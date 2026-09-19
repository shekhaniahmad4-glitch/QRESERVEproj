"""
===========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University – Bustos Campus
===========================================================
"""

from flask import Flask

from routes.auth import auth
from database import db, QueueCounter, QueueRequest
from extensions import limiter


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

    # Seed default counters
    _seed_counters(app)

    return app


# -----------------------------------------------------------
# Run Application
# -----------------------------------------------------------

app = create_app()


if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )