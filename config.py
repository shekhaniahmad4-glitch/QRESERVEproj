"""
===========================================================
QRESERVE
Application Configuration
===========================================================
"""

import os


class Config:

    SECRET_KEY = os.environ.get(
        "SECRET_KEY"
    ) or "qreserve_secret_key_change_me"

    # -------------------------------------------------------
    # Temporary Administrator Account
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

    SQLALCHEMY_DATABASE_URI = "sqlite:///qreserve.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # -------------------------------------------------------
    # PUBLIC BASE URL
    # -------------------------------------------------------
    #
    # The address that gets encoded into the QR code on the queue
    # card. It MUST be reachable from a phone on the same network
    # (or on the public internet) -- "localhost" / "127.0.0.1" will
    # NOT work, because the phone would look up its own machine.
    #
    # Local testing over Wi-Fi:
    #   set PUBLIC_BASE_URL=http://<your-LAN-IP>:5000
    #
    # Production:
    #   set PUBLIC_BASE_URL=https://qreserve.example.com
    #
    # Leave empty to fall back to the host the page was served from.
    # -------------------------------------------------------

    PUBLIC_BASE_URL = os.environ.get(
        "PUBLIC_BASE_URL",
        ""
    ).rstrip("/")

    # -------------------------------------------------------
    # EMAIL / SMTP
    # -------------------------------------------------------
    #
    # QRESERVE will use this email account to SEND OTPs.
    #
    # Example:
    #
    # MAIL_USERNAME = "qreserve@gmail.com"
    # MAIL_PASSWORD = "your-16-character-app-password"
    #
    # IMPORTANT:
    # MAIL_PASSWORD should be a Gmail APP PASSWORD,
    # NOT your normal Gmail password.
    #
    # -------------------------------------------------------

    MAIL_SERVER = os.environ.get(
        "MAIL_SERVER"
    ) or "smtp.gmail.com"

    MAIL_PORT = int(
        os.environ.get(
            "MAIL_PORT",
            587
        )
    )

    MAIL_USE_TLS = True

    MAIL_USERNAME = os.environ.get(
        "MAIL_USERNAME"
    ) or "qreserve.yourproject@gmail.com"

    MAIL_PASSWORD = os.environ.get(
        "MAIL_PASSWORD"
    ) or "orthhaybmgixihjq"

    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER"
    ) or MAIL_USERNAME

    # -------------------------------------------------------
    # OTP SETTINGS
    # -------------------------------------------------------

    OTP_EXPIRATION_MINUTES = 5  