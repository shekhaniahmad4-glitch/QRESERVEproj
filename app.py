"""
===========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University – Bustos Campus
===========================================================
"""

from flask import Flask

from routes.auth import auth
from database import db, QueueCounter
from extensions import limiter


def _seed_counters(app):
    """Seed the three default service counters if they don't exist yet."""
    with app.app_context():
        defaults = [
            {"counter_code": "A", "counter_name": "A Registrar",  "now_serving_prefix": "A"},
            {"counter_code": "B", "counter_name": "B Cashier",    "now_serving_prefix": "B"},
            {"counter_code": "C", "counter_name": "C Admissions", "now_serving_prefix": "C"},
        ]
        for row in defaults:
            existing = QueueCounter.query.filter_by(counter_code=row["counter_code"]).first()
            if not existing:
                counter = QueueCounter(
                    counter_code=row["counter_code"],
                    counter_name=row["counter_name"],
                    now_serving_prefix=row["now_serving_prefix"],
                    now_serving_number=0,
                    is_active=True,
                )
                db.session.add(counter)
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