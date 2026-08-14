"""
===========================================================
QRESERVE
Application Configuration
===========================================================
"""

import os


class Config:
    """
    Base configuration for the QRESERVE application.
    """

    # Flask Secret Key
    SECRET_KEY = os.environ.get(
        "SECRET_KEY"
    ) or "qreserve_secret_key_change_me"

    # -------------------------------------------------------
    # Temporary Administrator Account
    # We will move this to MySQL later.
    # -------------------------------------------------------

    ADMIN_EMAIL = os.environ.get(
        "ADMIN_EMAIL"
    ) or "admin@qreserve.com"

    ADMIN_PASSWORD = os.environ.get(
        "ADMIN_PASSWORD"
    ) or "admin123"

    # -------------------------------------------------------
    # Database
    # -------------------------------------------------------

    SQLALCHEMY_DATABASE_URI = ""

    SQLALCHEMY_TRACK_MODIFICATIONS = False