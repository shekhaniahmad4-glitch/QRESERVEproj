"""
===========================================================
QRESERVE
Database Models
===========================================================
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


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
        default=datetime.utcnow
    )


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
        default=datetime.utcnow,
        onupdate=datetime.utcnow
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

    wait_time = db.Column(
        db.String(50),
        default="10–15 minutes"
    )

    transaction_id = db.Column(
        db.String(50),
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="Processing"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    student = db.relationship(
        "Student",
        backref=db.backref("requests", cascade="all, delete-orphan")
    )

    def to_dict(self):
        return {
            "id": f"qrs-{self.id}",
            "db_id": self.id,
            "docName": self.doc_name,
            "queueNum": self.queue_number,
            "dateTime": self.created_at.strftime("%B %d, %Y %I:%M %p"),
            "status": self.status,
            "service": self.service,
            "counter": self.counter,
            "waitTime": self.wait_time,
            "transactionId": self.transaction_id,
            "dateGroup": self.created_at.strftime("%B %Y")
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

    is_active = db.Column(
        db.Boolean,
        default=True
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    @property
    def now_serving(self):
        """Returns formatted ticket string, e.g. A-007"""
        if self.now_serving_number == 0:
            return "---"
        return f"{self.now_serving_prefix}-{self.now_serving_number:03d}"

    @property
    def waiting_count(self):
        """Count active (Processing) QueueRequests for this counter."""
        counter_label = self.counter_name  # e.g. "A Registrar"
        return QueueRequest.query.filter(
            QueueRequest.status == "Processing"
        ).count()

    def to_dict(self):
        return {
            "id": self.id,
            "counter_code": self.counter_code,
            "counter_name": self.counter_name,
            "now_serving": self.now_serving,
            "now_serving_number": self.now_serving_number,
            "waiting_count": self.waiting_count,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<QueueCounter {self.counter_name} serving={self.now_serving}>"

