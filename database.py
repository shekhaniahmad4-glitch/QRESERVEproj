"""
===========================================================
QRESERVE
Database Models
===========================================================
"""

import re
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime, timezone, timedelta

# Philippine Standard Time (PST, UTC+8)
PHILIPPINES_TZ = timezone(timedelta(hours=8))

def ph_now():
    """Return current naive datetime in Philippine Standard Time (UTC+8)."""
    return datetime.now(PHILIPPINES_TZ).replace(tzinfo=None)


# -------------------------------------------------------
# Database Object
# -------------------------------------------------------

db = SQLAlchemy()


# -------------------------------------------------------
# Student Model
# -------------------------------------------------------

class Student(db.Model):

    __tablename__ = "students"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=ph_now
    )


    def to_dict(self):
        p = self.profile
        name = p.full_name if p and p.full_name else self.email.split("@")[0].replace(".", " ").title()
        
        email_prefix = self.email.split("@")[0]
        student_num = email_prefix if email_prefix.isdigit() else f"2026-{self.id:04d}"

        active_req_count = 0
        if self.requests:
            active_req_count = sum(1 for r in self.requests if r.status in ("Processing", "Ready for pickup"))

        return {
            "id": self.id,
            "student_number": student_num,
            "email": self.email,
            "full_name": name,
            "course": (p.course if p and p.course else "—"),
            "year_level": (p.year_level if p and p.year_level else "—"),
            "section": (p.section if p and p.section else "—"),
            "age": (p.age if p and p.age else "—"),
            "profile_pic": (p.profile_pic if p and p.profile_pic else None),
            "created_at": self.created_at.strftime("%B %d, %Y %I:%M %p") if self.created_at else "—",
            "date_joined": self.created_at.strftime("%b %d, %Y") if self.created_at else "—",
            "total_requests": len(self.requests) if self.requests else 0,
            "active_requests": active_req_count
        }

    def __repr__(self):

        return f"<Student {self.email}>"


# -------------------------------------------------------
# Student Profile Model
# -------------------------------------------------------

class StudentProfile(db.Model):

    __tablename__ = "student_profiles"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    full_name = db.Column(
        db.String(150),
        nullable=True
    )

    age = db.Column(
        db.Integer,
        nullable=True
    )

    course = db.Column(
        db.String(150),
        nullable=True
    )

    year_level = db.Column(
        db.String(20),
        nullable=True
    )

    section = db.Column(
        db.String(50),
        nullable=True
    )

    profile_pic = db.Column(
        db.String(255),
        nullable=True
    )

    updated_at = db.Column(
        db.DateTime,
        default=ph_now,
        onupdate=ph_now
    )

    student = db.relationship(
        "Student",
        backref=db.backref("profile", uselist=False, cascade="all, delete-orphan")
    )

    def __repr__(self):

        return f"<StudentProfile student_id={self.student_id}>"


# -------------------------------------------------------
# Queue Request Model
# -------------------------------------------------------

class QueueRequest(db.Model):

    __tablename__ = "queue_requests"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True
    )

    guest_session_key = db.Column(
        db.String(100),
        nullable=True
    )

    doc_name = db.Column(
        db.String(150),
        nullable=False
    )

    # List of selected items for this queue entry:
    # [{"name": "...", "type": "academic"|"payment", "price": 100}, ...]
    items = db.Column(
        db.JSON,
        nullable=True,
        default=list
    )

    queue_number = db.Column(
        db.String(20),
        nullable=False
    )

    counter = db.Column(
        db.String(50),
        default="Counter 4"
    )

    service = db.Column(
        db.String(100),
        default="Registrar – Document request"
    )

    price = db.Column(
        db.Integer,
        default=100
    )

    wait_time = db.Column(
        db.String(50),
        default="3–5 minutes"
    )

    transaction_id = db.Column(
        db.String(50),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="Processing"
    )

    # Two-step flow for document requests:
    # "payment"   → user is in Cashier queue (C-xxx), waiting to pay ₱100
    # "processing" → payment confirmed, user is in Registrar queue (A-xxx / B-xxx)
    # None         → Cashier-only requests (no Registrar step)
    queue_step = db.Column(
        db.String(20),
        nullable=True,
        default=None
    )

    guest_name = db.Column(
        db.String(100),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=ph_now
    )

    counter_turn_done = db.Column(
        db.Boolean,
        default=False
    )

    student = db.relationship(
        "Student",
        backref=db.backref("requests", cascade="all, delete-orphan")
    )

    @property
    def is_now_serving(self):
        """Check if this request's queue ticket is currently being called/served at its counter."""
        if not self.counter or not self.queue_number or self.counter_turn_done:
            return False
        if self.status not in ("Processing", "Ready for pickup"):
            return False

        m = re.search(r"([A-Z])-(\d+)", self.queue_number or "")
        if not m:
            return False
        prefix = m.group(1)
        num = int(m.group(2))

        counter = QueueCounter.query.filter(
            or_(
                QueueCounter.counter_name == self.counter,
                QueueCounter.now_serving_prefix == prefix,
                QueueCounter.counter_code == prefix
            )
        ).first()

        if not counter or counter.now_serving_number == 0:
            return False
        return counter.now_serving_number == num

    @property
    def estimated_wait(self):
        """Live estimate:
        If counter turn is already done:
          - Ready for pickup -> 'Ready for Pickup'
          - Processing -> 'Processing (Est. 3–5 days)'
        If waiting for counter:
          - Now Serving -> 'Now Serving'
          - Next in line -> 'Next in line'
          - ~3–5 minutes for each person ahead
        """
        if self.status == "Completed":
            return "Completed"

        if self.status == "Ready for pickup":
            return "Ready for Pickup"

        if self.counter_turn_done:
            return "Processing (Est. 3–5 days)"

        if self.is_now_serving:
            return "Now Serving"

        ahead = self.ahead_count
        if ahead == 0:
            return "Next in line"
        if ahead == 1:
            return "3–5 minutes"
        return f"{ahead * 3}–{ahead * 5} minutes"

    @property
    def ahead_count(self):
        """Number of active requests ahead in the same counter's queue and same step
        that haven't completed their counter turn yet."""
        if self.status not in ("Processing", "Ready for pickup") or self.counter_turn_done:
            return -1

        filters = [
            QueueRequest.counter == self.counter,
            QueueRequest.status.in_(["Processing", "Ready for pickup"]),
            QueueRequest.counter_turn_done.is_(False),
            QueueRequest.id < self.id,
        ]

        # Only count requests in the same queue step
        if self.queue_step is not None:
            filters.append(QueueRequest.queue_step == self.queue_step)

        return QueueRequest.query.filter(*filters).count()

    @property
    def total_price(self):
        """Total price across all selected items (defaults to price column)."""
        if self.items:
            return sum(int(it.get("price") or 0) for it in self.items)
        return self.price or 0

    @property
    def has_academic_items(self):
        """Whether this request contains academic-record items needing Registrar processing."""
        if not self.items:
            return True
        return any(it.get("type") == "academic" for it in self.items)

    @property
    def item_names(self):
        """Human-friendly summary of all items."""
        if not self.items:
            return self.doc_name
        return ", ".join(it.get("name", "") for it in self.items)

    def to_dict(self):
        step_label = None
        if self.queue_step == "payment":
            step_label = "Awaiting Payment"
        elif self.counter_turn_done or self.queue_step == "document_processing":
            step_label = "Document Processing"
        elif self.queue_step == "processing":
            step_label = "Waiting for Counter"

        user_type = "Student" if self.student_id else "Guest"
        if self.student:
            if self.student.profile and self.student.profile.full_name:
                user_name = self.student.profile.full_name
            else:
                user_name = self.student.email.split("@")[0]
            user_identifier = self.student.email
        else:
            user_name = self.guest_name or "Guest User"
            user_identifier = self.guest_name or (f"Guest #{self.guest_session_key[-6:]}" if self.guest_session_key else "Guest")

        return {
            "id": f"qrs-{self.id}",
            "db_id": self.id,
            "docName": self.item_names,
            "items": self.items or [],
            "queueNum": self.queue_number,
            "dateTime": self.created_at.strftime("%B %d, %Y %I:%M %p"),
            "status": self.status,
            "service": self.service,
            "counter": self.counter,
            "price": self.total_price,
            "waitTime": self.estimated_wait,
            "aheadCount": self.ahead_count,
            "isNowServing": self.is_now_serving,
            "queueStep": self.queue_step,
            "queueStepLabel": step_label,
            "counterTurnDone": bool(self.counter_turn_done),
            "hasAcademicItems": self.has_academic_items,
            "transactionId": self.transaction_id,
            "dateGroup": self.created_at.strftime("%B %Y"),
            "userType": user_type,
            "userName": user_name,
            "userIdentifier": user_identifier,
            "studentId": self.student_id
        }

    def __repr__(self):
        return f"<QueueRequest id={self.id} doc={self.doc_name} status={self.status}>"


# -------------------------------------------------------
# Queue Counter Model
# -------------------------------------------------------

class QueueCounter(db.Model):

    __tablename__ = "queue_counters"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    counter_code = db.Column(
        db.String(10),
        unique=True,
        nullable=False
    )  # "A", "B", "C"

    counter_name = db.Column(
        db.String(100),
        nullable=False
    )  # "A Registrar", "B Cashier", "C Admissions"

    now_serving_prefix = db.Column(
        db.String(5),
        nullable=False,
        default="A"
    )  # Letter prefix for now_serving (matches counter_code)

    now_serving_number = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )  # The numeric part of the ticket being served

    # Highest numeric ticket ever assigned to this counter's prefix.
    # Used to generate the next queue number (last_number + 1). Persisted
    # so it keeps counting even when requests are moved/removed.
    last_number = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    is_active = db.Column(
        db.Boolean,
        default=True
    )

    # Strict alternation for Registrar: which prefix was assigned LAST.
    # "A" → next goes to "B"; "B" → next goes to "A"; None → A first.
    last_registrar_prefix = db.Column(
        db.String(5),
        nullable=True,
        default=None
    )

    updated_at = db.Column(
        db.DateTime,
        default=ph_now,
        onupdate=ph_now
    )

    @property
    def now_serving(self):
        """Returns formatted ticket string, e.g. A-007"""
        if self.now_serving_number == 0:
            return "---"
        return f"{self.now_serving_prefix}-{self.now_serving_number:03d}"

    @property
    def waiting_count(self):
        """Count active QueueRequests waiting to be called at this counter window."""
        if self.counter_code == "C":
            return QueueRequest.query.filter(
                db.or_(
                    QueueRequest.queue_step == "payment",
                    QueueRequest.counter.like("%Cashier%")
                ),
                QueueRequest.status.in_(["Processing", "Ready for pickup"])
            ).count()

        return QueueRequest.query.filter(
            QueueRequest.counter == self.counter_name,
            QueueRequest.status.in_(["Processing", "Ready for pickup"]),
            QueueRequest.counter_turn_done.is_(False)
        ).count()

    def to_dict(self):
        return {
            "id": self.id,
            "counter_code": self.counter_code,
            "counter_name": self.counter_name,
            "now_serving_prefix": self.now_serving_prefix or self.counter_code,
            "now_serving": self.now_serving,
            "now_serving_number": self.now_serving_number,
            "waiting_count": self.waiting_count,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<QueueCounter {self.counter_name} serving={self.now_serving}>"

