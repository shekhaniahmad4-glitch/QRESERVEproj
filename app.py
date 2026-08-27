"""
===========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University – Bustos Campus
===========================================================
"""

from flask import Flask

from routes.auth import auth
from database import db
from extensions import limiter


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