"""
===========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University – Bustos Campus
===========================================================
"""

from flask import Flask, current_app, request
from urllib.parse import urlparse
import os
import socket

from datetime import timedelta
from routes.auth import auth
from database import db, QueueCounter, QueueRequest, AuditLog, ph_now
from extensions import limiter


def _seed_audit_logs(app):
    """Seed initial historical audit logs if table is empty (Week 14: Audit Logs)."""
    with app.app_context():
        if AuditLog.query.count() == 0:
            initial_logs = [
                AuditLog(action="ADMIN_LOGIN", actor_type="Admin", actor_name="admin", target="Admin Portal", details="Administrator signed in to QRESERVE admin dashboard", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, hours=2)),
                AuditLog(action="TICKET_CREATED", actor_type="Student", actor_name="Ahmad Shekhani", target="A-001", details="New queue request created for True Copy Certificate of Registration", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, hours=1, minutes=45)),
                AuditLog(action="PAYMENT_CONFIRMED", actor_type="Admin", actor_name="admin", target="A-001", details="Cashier confirmed payment of ₱100.00", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, hours=1, minutes=30)),
                AuditLog(action="CALL_NEXT", actor_type="Admin", actor_name="admin", target="Counter 1 – Registrar -> A-001", details="Called ticket A-001 at Counter 1 – Registrar", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, hours=1, minutes=10)),
                AuditLog(action="STATUS_CHANGE", actor_type="Admin", actor_name="admin", target="A-001", details="Status changed to 'Completed'. Document released to student.", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, hours=1)),
                AuditLog(action="TICKET_CREATED", actor_type="Student", actor_name="Ahmad Shekhani", target="B-001", details="New queue request created for True Copy Certificate of Registration", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, minutes=50)),
                AuditLog(action="PAYMENT_CONFIRMED", actor_type="Admin", actor_name="admin", target="B-001", details="Cashier confirmed payment of ₱100.00", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, minutes=40)),
                AuditLog(action="CALL_NEXT", actor_type="Admin", actor_name="admin", target="Counter 2 – Registrar -> B-001", details="Called ticket B-001 at Counter 2 – Registrar", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, minutes=20)),
                AuditLog(action="STATUS_CHANGE", actor_type="Admin", actor_name="admin", target="B-001", details="Status changed to 'Completed'. Document released to student.", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=4, minutes=5)),
                AuditLog(action="TICKET_CREATED", actor_type="Student", actor_name="Ahmad Shekhani", target="B-002", details="New queue request created for True Copy Certificate of Registration", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=3, hours=5)),
                AuditLog(action="PAYMENT_CONFIRMED", actor_type="Admin", actor_name="admin", target="B-002", details="Cashier confirmed payment of ₱100.00", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=3, hours=4)),
                AuditLog(action="CALL_NEXT", actor_type="Admin", actor_name="admin", target="Counter 2 – Registrar -> B-002", details="Called ticket B-002 at Counter 2 – Registrar", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=3, hours=3)),
                AuditLog(action="COMPLETE_WINDOW_TURN", actor_type="Admin", actor_name="admin", target="B-002", details="Counter window turn completed. Ticket moved to document back-office processing (Est. 3-5 days).", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=3, hours=2)),
                AuditLog(action="TICKET_CREATED", actor_type="Student", actor_name="Ahmad Shekhani", target="A-003", details="New queue request created for True Copy Report of Grades", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=2, hours=1)),
                AuditLog(action="PAYMENT_CONFIRMED", actor_type="Admin", actor_name="admin", target="A-003", details="Cashier confirmed payment of ₱100.00", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=2, minutes=50)),
                AuditLog(action="CALL_NEXT", actor_type="Admin", actor_name="admin", target="Counter 1 – Registrar -> A-003", details="Called ticket A-003 at Counter 1 – Registrar", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=2, minutes=30)),
                AuditLog(action="STATUS_CHANGE", actor_type="Admin", actor_name="admin", target="A-003", details="Status changed to 'Completed'. Document released to student.", ip_address="127.0.0.1", created_at=ph_now() - timedelta(days=2, minutes=10)),
            ]
            for l in initial_logs:
                db.session.add(l)
            db.session.commit()



def _seed_counters(app):
    """Seed the default service counters if they don't exist yet."""
    with app.app_context():
        defaults = [
            {"counter_code": "A", "counter_name": "Counter 1 – Registrar", "now_serving_prefix": "A"},
            {"counter_code": "B", "counter_name": "Counter 2 – Registrar", "now_serving_prefix": "B"},
            {"counter_code": "C", "counter_name": "Counter 3 – Cashier",   "now_serving_prefix": "C"},
        ]
        for row in defaults:
            existing = QueueCounter.query.filter_by(counter_code=row["counter_code"]).first()
            if existing:
                # Keep names in sync with the current schema
                existing.counter_name = row["counter_name"]
                existing.now_serving_prefix = row["now_serving_prefix"]
                continue
            counter = QueueCounter(
                counter_code=row["counter_code"],
                counter_name=row["counter_name"],
                now_serving_prefix=row["now_serving_prefix"],
                now_serving_number=0,
                is_active=True,
            )
            db.session.add(counter)
        db.session.commit()

        # Initialize last_number from the highest existing ticket per prefix
        for counter in QueueCounter.query.all():
            prefix = counter.now_serving_prefix
            requests = QueueRequest.query.filter(
                QueueRequest.queue_number.like(prefix + "-%")
            ).all()
            max_num = 0
            for r in requests:
                for part in (r.queue_number or "").split():
                    if part.startswith(prefix + "-"):
                        num = part.split("-")[1]
                        if num.isdigit() and int(num) > max_num:
                            max_num = int(num)
            counter.last_number = max(counter.last_number or 0, max_num)
        db.session.commit()


def create_app():

    app = Flask(__name__)

    # Load configuration
    app.config.from_object("config.Config")

    # Initialize database
    db.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    # Register authentication routes
    app.register_blueprint(auth)

    # Create database tables
    with app.app_context():
        db.create_all()

        # Migration: add 'price' column to queue_requests if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_requests)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "price" not in columns:
                conn.execute(db.text("ALTER TABLE queue_requests ADD COLUMN price INTEGER DEFAULT 100"))
                conn.commit()

        # Migration: add 'last_number' column to queue_counters if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_counters)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "last_number" not in columns:
                conn.execute(db.text("ALTER TABLE queue_counters ADD COLUMN last_number INTEGER DEFAULT 0"))
                conn.commit()

        # Migration: add 'last_registrar_prefix' column to queue_counters if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_counters)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "last_registrar_prefix" not in columns:
                conn.execute(db.text("ALTER TABLE queue_counters ADD COLUMN last_registrar_prefix VARCHAR(5)"))
                conn.commit()

        # Migration: add 'queue_step' column to queue_requests if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_requests)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "queue_step" not in columns:
                conn.execute(db.text("ALTER TABLE queue_requests ADD COLUMN queue_step VARCHAR(20)"))
                conn.commit()

        # Migration: add 'items' JSON column to queue_requests if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_requests)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "items" not in columns:
                conn.execute(db.text("ALTER TABLE queue_requests ADD COLUMN items TEXT"))
                conn.commit()

        # Migration: add 'guest_name' column to queue_requests if missing
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_requests)")
            )
            columns = [row[1] for row in result.fetchall()]
            if "guest_name" not in columns:
                conn.execute(db.text("ALTER TABLE queue_requests ADD COLUMN guest_name VARCHAR(100)"))
                conn.commit()

        # Migration: receipt timestamps (paid_at, completed_at)
        with db.engine.connect() as conn:
            result = conn.execute(
                db.text("PRAGMA table_info(queue_requests)")
            )
            columns = [row[1] for row in result.fetchall()]
            for col in ("paid_at", "completed_at"):
                if col not in columns:
                    conn.execute(db.text(f"ALTER TABLE queue_requests ADD COLUMN {col} DATETIME"))
            if "contact_email" not in columns:
                conn.execute(db.text("ALTER TABLE queue_requests ADD COLUMN contact_email VARCHAR(120)"))
            conn.commit()

    # Seed default counters
    _seed_counters(app)

    # Seed initial audit logs (Week 14)
    _seed_audit_logs(app)

    _register_base_url(app)

    return app


def _register_base_url(app):
    """Expose the address encoded into the queue-card QR code.

    The QR must point at a host a phone can reach, so we prefer the
    configured PUBLIC_BASE_URL and fall back to whatever host served the
    request. Local addresses are flagged so the UI can warn the user
    instead of silently handing out a QR code that cannot be scanned
    from another device.
    """

    @app.context_processor
    def inject_base_url():
        configured = current_app.config.get("PUBLIC_BASE_URL") or ""
        base = configured or request.host_url.rstrip("/")
        # Opened via localhost? A phone can't reach that, so encode this
        # machine's Wi-Fi address instead (same port).
        if not configured and _is_local_host(base):
            lan = _lan_ip()
            if lan:
                port = urlparse(base).port
                base = f"{urlparse(base).scheme}://{lan}" + (f":{port}" if port else "")
        return {
            "public_base_url": base,
            "public_base_url_is_local": _is_local_host(base)
        }

    def _is_local_host(base):
        host = urlparse(base).hostname or ""
        host = host.lower()
        return (
            host in ("localhost", "::1", "0.0.0.0", "")
            or host.startswith("127.")
        )


def _lan_ip():
    """Best-effort LAN IPv4 of this machine (no packets are actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        s.close()


# -----------------------------------------------------------
# Run Application
# -----------------------------------------------------------

app = create_app()


if __name__ == "__main__":

    # Bind address for `python app.py`. Defaults to 0.0.0.0 so phones on the
    # same Wi-Fi can scan and open QR codes / receipts.
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))

    lan = _lan_ip()
    base = app.config.get("PUBLIC_BASE_URL") or f"http://{lan or 'localhost'}:{PORT}"
    print("=" * 60, flush=True)
    print("QRESERVE", flush=True)
    print(f"Local access:    http://localhost:{PORT}", flush=True)
    if lan:
        print(f"Mobile (Wi-Fi):  http://{lan}:{PORT}", flush=True)
        print(f"QR codes encode: {base}/ticket/<transaction_id>", flush=True)
    print("=" * 60, flush=True)

    if HOST not in ("127.0.0.1", "localhost"):
        print(
            "WARNING: bound to a public interface with debug=True, which exposes "
            "the Werkzeug console. Use debug=False for anything but local testing.",
            flush=True,
        )

    app.run(
        debug=True,
        host=HOST,
        port=PORT
    )