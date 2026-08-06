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
    SECRET_KEY = os.environ.get("SECRET_KEY") or "qreserve_secret_key_change_me"

    # Database configuration (we will connect MySQL later)
    SQLALCHEMY_DATABASE_URI = ""
    SQLALCHEMY_TRACK_MODIFICATIONS = False