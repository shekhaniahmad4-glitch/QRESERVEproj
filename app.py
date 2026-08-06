"""
===========================================================
QRESERVE
Online Queue & Monitoring System
Bulacan State University – Bustos Campus

Main Application File
===========================================================
"""

from flask import Flask
from routes.auth import auth


def create_app():
    """
    Application Factory

    Creates and configures the Flask application.
    """

    app = Flask(__name__)
    app.config.from_object("config.Config")
    app.register_blueprint(auth)

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