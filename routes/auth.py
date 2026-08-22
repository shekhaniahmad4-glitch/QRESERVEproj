from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app
)

import re
import secrets
import smtplib
import threading

from datetime import datetime, timedelta
from email.message import EmailMessage

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import db, Student


auth = Blueprint("auth", __name__)


# =======================================================
# SEND OTP EMAIL
# =======================================================

def send_otp_email(recipient_email, otp):

    sender_email = current_app.config["MAIL_USERNAME"]
    sender_password = current_app.config["MAIL_PASSWORD"]
    smtp_server = current_app.config["MAIL_SERVER"]
    smtp_port = current_app.config["MAIL_PORT"]

    # ---------------------------------------------------
    # Create email
    # ---------------------------------------------------

    message = EmailMessage()

    message["Subject"] = "QRESERVE - Student Account Verification"
    message["From"] = sender_email
    message["To"] = recipient_email

    message.set_content(
        f"""\
Hello,

You are creating a student account for QRESERVE.

Your verification code is:

{otp}

This OTP will expire in 5 minutes.

If you did not request this account, you can safely ignore this email.

--------------------------------------------------
QRESERVE
Bulacan State University - Bustos Campus
--------------------------------------------------
"""
    )

    # ---------------------------------------------------
    # Connect to Gmail SMTP
    # ---------------------------------------------------

    try:

        with smtplib.SMTP(
            smtp_server,
            smtp_port,
            timeout=10
        ) as server:

            server.ehlo()

            server.starttls()

            server.ehlo()

            server.login(
                sender_email,
                sender_password
            )

            server.send_message(message)

        print("=" * 60, flush=True)
        print("QRESERVE OTP EMAIL SENT", flush=True)
        print("TO:", recipient_email, flush=True)
        print("STATUS: SUCCESS", flush=True)
        print("=" * 60, flush=True)

    except Exception as e:

        print("=" * 60, flush=True)
        print("QRESERVE OTP EMAIL ERROR", flush=True)
        print("TO:", recipient_email, flush=True)
        print("ERROR:", e, flush=True)
        print("=" * 60, flush=True)


# =======================================================
# BACKGROUND OTP EMAIL
# =======================================================

def send_otp_email_background(recipient_email, otp):

    # ---------------------------------------------------
    # Copy the Flask application object.
    #
    # This allows the background thread to safely access
    # current_app configuration.
    # ---------------------------------------------------

    app = current_app._get_current_object()

    def send():

        with app.app_context():

            send_otp_email(
                recipient_email,
                otp
            )

    thread = threading.Thread(
        target=send,
        daemon=True
    )

    thread.start()


# =======================================================
# STUDENT LOGIN
# =======================================================

@auth.route("/", methods=["GET", "POST"])
@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        student = Student.query.filter_by(
            email=email
        ).first()

        if student is None or not check_password_hash(
            student.password_hash,
            password
        ):

            flash(
                "Invalid email or password.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        session.clear()

        session["student_id"] = student.id
        session["student_email"] = student.email

        flash(
            "Login successful!",
            "success"
        )

        return redirect(
            url_for("auth.student_dashboard")
        )

    return render_template(
        "login.html"
    )


# =======================================================
# STUDENT SIGN UP
# =======================================================

@auth.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    # ---------------------------------------------------
    # GET
    # ---------------------------------------------------

    if request.method == "GET":

        return render_template(
            "sign_up.html"
        )

    # ---------------------------------------------------
    # Get form data
    # ---------------------------------------------------

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    # ---------------------------------------------------
    # Required fields
    # ---------------------------------------------------

    if not email or not password or not confirm_password:

        flash(
            "Please complete all fields.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # BULSU STUDENT EMAIL VALIDATION
    #
    # Required:
    #
    # 2024200791@ms.bulsu.edu.ph
    #
    # Exactly 10 digits before @ms.bulsu.edu.ph
    # ---------------------------------------------------

    bulsu_email_pattern = (
        r"^\d{10}@ms\.bulsu\.edu\.ph$"
    )

    if not re.match(
        bulsu_email_pattern,
        email
    ):

        flash(
            "Please use a valid BulSU student email "
            "(example: 2024200791@ms.bulsu.edu.ph).",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Confirm password
    # ---------------------------------------------------

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Password length
    # ---------------------------------------------------

    if len(password) < 8:

        flash(
            "Password must be at least 8 characters long.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Uppercase
    # ---------------------------------------------------

    if not re.search(
        r"[A-Z]",
        password
    ):

        flash(
            "Password must contain at least one capital letter.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Number
    # ---------------------------------------------------

    if not re.search(
        r"[0-9]",
        password
    ):

        flash(
            "Password must contain at least one number.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Special character
    # ---------------------------------------------------

    if not re.search(
        r"[^A-Za-z0-9]",
        password
    ):

        flash(
            "Password must contain at least one special character.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # Check existing student account
    # ---------------------------------------------------

    existing_student = Student.query.filter_by(
        email=email
    ).first()

    if existing_student:

        flash(
            "This email is already registered.",
            "danger"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # GENERATE OTP
    # ---------------------------------------------------

    otp = str(
        secrets.randbelow(900000) + 100000
    )

    # ---------------------------------------------------
    # Store pending registration
    # ---------------------------------------------------

    session["pending_registration"] = {

        "email": email,

        "password_hash": generate_password_hash(
            password
        ),

        "otp": otp,

        "expires_at": (
            datetime.utcnow()
            + timedelta(
                minutes=current_app.config[
                    "OTP_EXPIRATION_MINUTES"
                ]
            )
        ).isoformat()

    }

    # ---------------------------------------------------
    # SEND OTP IN BACKGROUND
    #
    # IMPORTANT:
    # We do NOT wait for Gmail to finish.
    # ---------------------------------------------------

    send_otp_email_background(
        email,
        otp
    )

    # ---------------------------------------------------
    # Immediately show OTP page
    # ---------------------------------------------------

    flash(
        "A verification code has been sent to your BulSU email.",
        "success"
    )

    return redirect(
        url_for("auth.verify_otp")
    )


# =======================================================
# STUDENT OTP VERIFICATION
# =======================================================

@auth.route(
    "/verify-otp",
    methods=["GET", "POST"]
)
def verify_otp():

    pending = session.get(
        "pending_registration"
    )

    # ---------------------------------------------------
    # No pending registration
    # ---------------------------------------------------

    if not pending:

        flash(
            "No pending registration found.",
            "warning"
        )

        return redirect(
            url_for("auth.signup")
        )

    # ---------------------------------------------------
    # POST - VERIFY OTP
    # ---------------------------------------------------

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp",
            ""
        ).strip()

        # ------------------------------------------------
        # Validate OTP format
        # ------------------------------------------------

        if not re.fullmatch(
            r"\d{6}",
            entered_otp
        ):

            flash(
                "Please enter the 6-digit verification code.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_otp")
            )

        # ------------------------------------------------
        # Check expiration
        # ------------------------------------------------

        expires_at = datetime.fromisoformat(
            pending["expires_at"]
        )

        if datetime.utcnow() > expires_at:

            session.pop(
                "pending_registration",
                None
            )

            flash(
                "Your OTP has expired. Please register again.",
                "danger"
            )

            return redirect(
                url_for("auth.signup")
            )

        # ------------------------------------------------
        # Check OTP
        # ------------------------------------------------

        if not secrets.compare_digest(
            entered_otp,
            pending["otp"]
        ):

            flash(
                "Invalid OTP. Please try again.",
                "danger"
            )

            return redirect(
                url_for("auth.verify_otp")
            )

        # ------------------------------------------------
        # Check existing account again
        # ------------------------------------------------

        existing_student = Student.query.filter_by(
            email=pending["email"]
        ).first()

        if existing_student:

            session.pop(
                "pending_registration",
                None
            )

            flash(
                "This email is already registered.",
                "danger"
            )

            return redirect(
                url_for("auth.login")
            )

        # ------------------------------------------------
        # CREATE STUDENT ACCOUNT
        # ------------------------------------------------

        new_student = Student(
            email=pending["email"],
            password_hash=pending["password_hash"]
        )

        db.session.add(
            new_student
        )

        db.session.commit()

        # ------------------------------------------------
        # Clear pending registration
        # ------------------------------------------------

        session.pop(
            "pending_registration",
            None
        )

        flash(
            "Account verification successful! "
            "Your student account has been created.",
            "success"
        )

        return redirect(
            url_for("auth.login")
        )

    # ---------------------------------------------------
    # GET - SHOW OTP PAGE
    # ---------------------------------------------------

    return render_template(
        "verify_otp.html",
        email=pending["email"]
    )


# =======================================================
# STUDENT DASHBOARD
# =======================================================

@auth.route(
    "/student/dashboard"
)
def student_dashboard():

    if not session.get(
        "student_id"
    ):

        flash(
            "Please log in first.",
            "warning"
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template(
        "student_dashboard.html"
    )


# =======================================================
# STUDENT LOGOUT
# =======================================================

@auth.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("auth.login")
    )


# =======================================================
# GUEST
# =======================================================

@auth.route("/guest")
def guest():

    return render_template(
        "guest_login.html"
    )


# =======================================================
# ADMIN LOGIN
# =======================================================

@auth.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        admin_email = current_app.config[
            "ADMIN_EMAIL"
        ]

        admin_password = current_app.config[
            "ADMIN_PASSWORD"
        ]

        if (
            email == admin_email
            and password == admin_password
        ):

            session.clear()

            session["admin_logged_in"] = True
            session["admin_email"] = email

            flash(
                "Administrator login successful!",
                "success"
            )

            return redirect(
                url_for("auth.admin_dashboard")
            )

        flash(
            "Invalid administrator email or password.",
            "danger"
        )

        return redirect(
            url_for("auth.admin_login")
        )

    return render_template(
        "admin_login.html"
    )


# =======================================================
# ADMIN DASHBOARD
# =======================================================

@auth.route(
    "/admin/dashboard"
)
def admin_dashboard():

    if not session.get(
        "admin_logged_in"
    ):

        flash(
            "Please log in as administrator first.",
            "warning"
        )

        return redirect(
            url_for("auth.admin_login")
        )

    return render_template(
        "admin_dashboard.html"
    )


# =======================================================
# ADMIN LOGOUT
# =======================================================

@auth.route(
    "/admin/logout"
)
def admin_logout():

    session.clear()

    flash(
        "Administrator logged out.",
        "success"
    )

    return redirect(
        url_for("auth.admin_login")
    )
