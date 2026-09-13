from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    jsonify
)

import os
import re
import secrets
import smtplib
import threading
import random

from datetime import datetime, timedelta
from email.message import EmailMessage

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from werkzeug.utils import secure_filename

from database import db, Student, StudentProfile, QueueRequest, QueueCounter

from extensions import limiter


auth = Blueprint("auth", __name__)


# =======================================================
# BULSU STUDENT EMAIL PATTERN
#
# Required:
#
# 2024200791@ms.bulsu.edu.ph
#
# Exactly 10 digits before @ms.bulsu.edu.ph
# =======================================================

BULSU_EMAIL_PATTERN = r"^\d{10}@ms\.bulsu\.edu\.ph$"


# =======================================================
# LOW-LEVEL EMAIL SENDER
# =======================================================

def _send_email(recipient_email, subject, body):

    sender_email = current_app.config["MAIL_USERNAME"]
    sender_password = current_app.config["MAIL_PASSWORD"]
    smtp_server = current_app.config["MAIL_SERVER"]
    smtp_port = current_app.config["MAIL_PORT"]

    # ---------------------------------------------------
    # Create email
    # ---------------------------------------------------

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email

    message.set_content(body)

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
# SEND OTP EMAIL (SIGN UP)
# =======================================================

def send_otp_email(recipient_email, otp):

    _send_email(
        recipient_email,
        "QRESERVE - Student Account Verification",
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


# =======================================================
# SEND OTP EMAIL (PASSWORD RECOVERY)
# =======================================================

def send_password_reset_otp_email(recipient_email, otp):

    _send_email(
        recipient_email,
        "QRESERVE - Account Recovery Verification",
        f"""\
Hello,

You requested to recover your student account for QRESERVE.

Your verification code is:

{otp}

This OTP will expire in 5 minutes.

If you did not request an account recovery, you can safely ignore this email.

--------------------------------------------------
QRESERVE
Bulacan State University - Bustos Campus
--------------------------------------------------
"""
    )


# =======================================================
# SEND OTP EMAIL (PROFILE UPDATE)
# =======================================================

def send_profile_update_otp_email(recipient_email, otp):

    _send_email(
        recipient_email,
        "QRESERVE - Profile Update Verification",
        f"""\
Hello,

You requested to update your personal information on QRESERVE.

Your verification code is:

{otp}

This OTP will expire in 5 minutes.

If you did not request this update, please check your account security immediately.

--------------------------------------------------
QRESERVE
Bulacan State University - Bustos Campus
--------------------------------------------------
"""
    )

# =======================================================
# BACKGROUND EMAIL SENDER
# =======================================================

def _send_in_background(target_function, recipient_email, otp):

    # ---------------------------------------------------
    # Copy the Flask application object.
    #
    # This allows the background thread to safely access
    # current_app configuration.
    # ---------------------------------------------------

    app = current_app._get_current_object()

    def send():

        with app.app_context():

            target_function(
                recipient_email,
                otp
            )

    thread = threading.Thread(
        target=send,
        daemon=True
    )

    thread.start()


def send_otp_email_background(recipient_email, otp):

    _send_in_background(
        send_otp_email,
        recipient_email,
        otp
    )


def send_password_reset_otp_email_background(recipient_email, otp):

    _send_in_background(
        send_password_reset_otp_email,
        recipient_email,
        otp
    )


# =======================================================
# PASSWORD REQUIREMENTS
# =======================================================

def password_requirement_error(password):

    if len(password) < 8:

        return "Password must be at least 8 characters long."

    if not re.search(r"[A-Z]", password):

        return "Password must contain at least one capital letter."

    if not re.search(r"[0-9]", password):

        return "Password must contain at least one number."

    if not re.search(r"[^A-Za-z0-9]", password):

        return "Password must contain at least one special character."

    return None


# =======================================================
# STUDENT LOGIN
# =======================================================

@auth.route("/", methods=["GET", "POST"])
@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
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
@limiter.limit("5 per minute")
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
    # ---------------------------------------------------

    if not re.match(
        BULSU_EMAIL_PATTERN,
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
    # Password requirements
    # ---------------------------------------------------

    password_error = password_requirement_error(password)

    if password_error:

        flash(
            password_error,
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
@limiter.limit("10 per minute")
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
# FORGOT PASSWORD - REQUEST CODE
# =======================================================

@auth.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute")
def forgot_password():

    # ---------------------------------------------------
    # GET
    # ---------------------------------------------------

    if request.method == "GET":

        return render_template(
            "forgot_password.html"
        )

    # ---------------------------------------------------
    # POST
    # ---------------------------------------------------

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    if not email:

        flash(
            "Please enter your BulSU student email.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    if not re.match(
        BULSU_EMAIL_PATTERN,
        email
    ):

        flash(
            "Please use a valid BulSU student email "
            "(example: 2024200791@ms.bulsu.edu.ph).",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # ---------------------------------------------------
    # Check that the account exists
    # ---------------------------------------------------

    student = Student.query.filter_by(
        email=email
    ).first()

    if student is None:

        flash(
            "No account was found with that email address.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # ---------------------------------------------------
    # GENERATE OTP
    # ---------------------------------------------------

    otp = str(
        secrets.randbelow(900000) + 100000
    )

    # ---------------------------------------------------
    # Store pending password reset
    # ---------------------------------------------------

    session["password_reset"] = {

        "email": email,

        "otp": otp,

        "expires_at": (
            datetime.utcnow()
            + timedelta(
                minutes=current_app.config[
                    "OTP_EXPIRATION_MINUTES"
                ]
            )
        ).isoformat(),

        "verified": False

    }

    # ---------------------------------------------------
    # SEND OTP IN BACKGROUND
    # ---------------------------------------------------

    send_password_reset_otp_email_background(
        email,
        otp
    )

    flash(
        "A verification code has been sent to your BulSU email.",
        "success"
    )

    return redirect(
        url_for("auth.verify_reset_otp")
    )


# =======================================================
# FORGOT PASSWORD - VERIFY OTP
# =======================================================

@auth.route(
    "/verify-reset-otp",
    methods=["GET", "POST"]
)
@limiter.limit("10 per minute")
def verify_reset_otp():

    pending = session.get(
        "password_reset"
    )

    # ---------------------------------------------------
    # No pending password reset
    # ---------------------------------------------------

    if not pending:

        flash(
            "No pending password recovery request found.",
            "warning"
        )

        return redirect(
            url_for("auth.forgot_password")
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
                url_for("auth.verify_reset_otp")
            )

        # ------------------------------------------------
        # Check expiration
        # ------------------------------------------------

        expires_at = datetime.fromisoformat(
            pending["expires_at"]
        )

        if datetime.utcnow() > expires_at:

            session.pop(
                "password_reset",
                None
            )

            flash(
                "Your OTP has expired. Please request a new one.",
                "danger"
            )

            return redirect(
                url_for("auth.forgot_password")
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
                url_for("auth.verify_reset_otp")
            )

        # ------------------------------------------------
        # Mark as verified
        # ------------------------------------------------

        pending["verified"] = True

        session["password_reset"] = pending

        flash(
            "Email verified. You may now set a new password.",
            "success"
        )

        return redirect(
            url_for("auth.reset_password")
        )

    # ---------------------------------------------------
    # GET - SHOW OTP PAGE
    # ---------------------------------------------------

    return render_template(
        "verify_reset_otp.html",
        email=pending["email"]
    )


# =======================================================
# FORGOT PASSWORD - RESEND OTP
# =======================================================

@auth.route(
    "/verify-reset-otp/resend"
)
@limiter.limit("3 per minute")
def resend_reset_otp():

    pending = session.get(
        "password_reset"
    )

    if not pending:

        flash(
            "No pending password recovery request found.",
            "warning"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # ---------------------------------------------------
    # GENERATE NEW OTP
    # ---------------------------------------------------

    otp = str(
        secrets.randbelow(900000) + 100000
    )

    pending["otp"] = otp

    pending["verified"] = False

    pending["expires_at"] = (
        datetime.utcnow()
        + timedelta(
            minutes=current_app.config[
                "OTP_EXPIRATION_MINUTES"
            ]
        )
    ).isoformat()

    session["password_reset"] = pending

    send_password_reset_otp_email_background(
        pending["email"],
        otp
    )

    flash(
        "A new verification code has been sent to your BulSU email.",
        "success"
    )

    return redirect(
        url_for("auth.verify_reset_otp")
    )


# =======================================================
# FORGOT PASSWORD - RESET PASSWORD
# =======================================================

@auth.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    pending = session.get(
        "password_reset"
    )

    if not pending or not pending.get("verified"):

        flash(
            "Please verify your email before resetting your password.",
            "warning"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    # ---------------------------------------------------
    # GET
    # ---------------------------------------------------

    if request.method == "GET":

        return render_template(
            "reset_password.html"
        )

    # ---------------------------------------------------
    # POST
    # ---------------------------------------------------

    new_password = request.form.get(
        "new_password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if not new_password or not confirm_password:

        flash(
            "Please complete all fields.",
            "danger"
        )

        return redirect(
            url_for("auth.reset_password")
        )

    if new_password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return redirect(
            url_for("auth.reset_password")
        )

    password_error = password_requirement_error(
        new_password
    )

    if password_error:

        flash(
            password_error,
            "danger"
        )

        return redirect(
            url_for("auth.reset_password")
        )

    # ---------------------------------------------------
    # Update account password
    # ---------------------------------------------------

    student = Student.query.filter_by(
        email=pending["email"]
    ).first()

    if student is None:

        session.pop(
            "password_reset",
            None
        )

        flash(
            "We could not find that account. Please try again.",
            "danger"
        )

        return redirect(
            url_for("auth.forgot_password")
        )

    student.password_hash = generate_password_hash(
        new_password
    )

    db.session.commit()

    session.pop(
        "password_reset",
        None
    )

    flash(
        "Your password has been reset successfully. Please log in.",
        "success"
    )

    return redirect(
        url_for("auth.login")
    )


# =======================================================
# STUDENT PROFILE
# =======================================================

ALLOWED_PIC_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _allowed_pic(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_PIC_EXTENSIONS
    )


@auth.route(
    "/student/profile",
    methods=["GET", "POST"]
)
def student_profile():

    if not session.get("student_id"):
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    student = Student.query.get(session["student_id"])
    profile = student.profile  # may be None

    # Check if student already has saved profile information
    is_existing_info = bool(profile and profile.full_name)

    if request.method == "POST":

        full_name  = request.form.get("full_name",  "").strip()
        age_raw    = request.form.get("age",        "").strip()
        course     = request.form.get("course",     "").strip()
        year_level = request.form.get("year_level", "").strip()
        section    = request.form.get("section",    "").strip()

        # Basic validation
        age = None
        if age_raw:
            if not age_raw.isdigit() or not (10 <= int(age_raw) <= 100):
                flash("Please enter a valid age (10–100).", "danger")
                return render_template(
                    "student_profile.html",
                    profile=profile
                )
            age = int(age_raw)

        # Profile picture upload
        pic_filename = profile.profile_pic if profile else None
        pic_file = request.files.get("profile_pic")

        if pic_file and pic_file.filename:
            if not _allowed_pic(pic_file.filename):
                flash("Only PNG, JPG, GIF, or WEBP images are allowed.", "danger")
                return render_template(
                    "student_profile.html",
                    profile=profile
                )

            upload_dir = os.path.join(
                current_app.static_folder, "profile_pics"
            )
            os.makedirs(upload_dir, exist_ok=True)

            ext = pic_file.filename.rsplit(".", 1)[1].lower()
            safe_name = f"student_{student.id}.{ext}"
            pic_file.save(os.path.join(upload_dir, safe_name))
            pic_filename = safe_name

        # If personal info was ALREADY initially provided:
        # Require password verification and email OTP
        if is_existing_info:
            current_password = request.form.get("current_password", "").strip()

            if not current_password:
                flash("Please enter your current account password to authorize changes.", "danger")
                return render_template(
                    "student_profile.html",
                    profile=profile
                )

            if not check_password_hash(student.password_hash, current_password):
                flash("Incorrect password. Please enter your valid account password to make changes.", "danger")
                return render_template(
                    "student_profile.html",
                    profile=profile
                )

            # Generate OTP for email verification
            otp = str(secrets.randbelow(900000) + 100000)

            session["pending_profile_update"] = {
                "student_id": student.id,
                "full_name": full_name or None,
                "age": age,
                "course": course or None,
                "year_level": year_level or None,
                "section": section or None,
                "pic_filename": pic_filename,
                "otp": otp,
                "expires_at": (
                    datetime.utcnow() + timedelta(minutes=5)
                ).isoformat()
            }

            _send_in_background(send_profile_update_otp_email, student.email, otp)

            flash("Password verified! A 6-digit verification code has been sent to your email to confirm profile changes.", "success")
            return redirect(url_for("auth.student_profile_verify_otp"))

        # Initial profile setup (first time): save directly
        if profile is None:
            profile = StudentProfile(student_id=student.id)
            db.session.add(profile)

        profile.full_name  = full_name  or None
        profile.age        = age
        profile.course     = course     or None
        profile.year_level = year_level or None
        profile.section    = section    or None
        profile.profile_pic = pic_filename

        db.session.commit()

        flash("Profile saved successfully!", "success")
        return redirect(url_for("auth.student_profile"))

    return render_template(
        "student_profile.html",
        profile=profile
    )


# =======================================================
# VERIFY PROFILE UPDATE OTP
# =======================================================

@auth.route("/student/profile/verify-otp", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def student_profile_verify_otp():

    if not session.get("student_id"):
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    student = Student.query.get(session["student_id"])
    pending = session.get("pending_profile_update")

    if not pending or pending.get("student_id") != student.id:
        flash("No pending profile update found.", "warning")
        return redirect(url_for("auth.student_profile"))

    if request.method == "POST":

        otp_input = request.form.get("otp", "").strip()

        # Check expiration
        try:
            expires_at = datetime.fromisoformat(pending["expires_at"])
            if datetime.utcnow() > expires_at:
                session.pop("pending_profile_update", None)
                flash("Verification code has expired. Please submit your update again.", "danger")
                return redirect(url_for("auth.student_profile"))
        except Exception:
            pass

        # Check match
        if otp_input != pending.get("otp"):
            flash("Invalid verification code. Please check your email and try again.", "danger")
            return render_template(
                "verify_profile_otp.html",
                email=student.email
            )

        # Verified! Apply changes to database
        profile = student.profile
        if profile is None:
            profile = StudentProfile(student_id=student.id)
            db.session.add(profile)

        profile.full_name  = pending.get("full_name")
        profile.age        = pending.get("age")
        profile.course     = pending.get("course")
        profile.year_level = pending.get("year_level")
        profile.section    = pending.get("section")
        if pending.get("pic_filename"):
            profile.profile_pic = pending.get("pic_filename")

        db.session.commit()
        session.pop("pending_profile_update", None)

        flash("Personal information updated successfully!", "success")
        return redirect(url_for("auth.student_profile"))

    return render_template(
        "verify_profile_otp.html",
        email=student.email
    )


# =======================================================
# RESEND PROFILE UPDATE OTP
# =======================================================

@auth.route("/student/profile/resend-otp")
@limiter.limit("3 per minute")
def student_profile_resend_otp():

    if not session.get("student_id"):
        return redirect(url_for("auth.login"))

    student = Student.query.get(session["student_id"])
    pending = session.get("pending_profile_update")

    if not pending or pending.get("student_id") != student.id:
        flash("No pending profile update found.", "warning")
        return redirect(url_for("auth.student_profile"))

    otp = str(secrets.randbelow(900000) + 100000)
    pending["otp"] = otp
    pending["expires_at"] = (
        datetime.utcnow() + timedelta(minutes=5)
    ).isoformat()
    session["pending_profile_update"] = pending

    _send_in_background(send_profile_update_otp_email, student.email, otp)

    flash("A fresh verification code has been sent to your email.", "success")
    return redirect(url_for("auth.student_profile_verify_otp"))


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

    student = Student.query.get(session["student_id"])
    profile = student.profile if student else None

    return render_template(
        "student_dashboard.html",
        profile=profile
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

@auth.route("/guest", methods=["GET", "POST"])
def guest():

    if request.method == "POST":

        guest_name     = request.form.get("guest_name",     "").strip()
        guest_category = request.form.get("guest_category", "").strip()

        # Store in session (optional — may be empty)
        session["guest_name"]     = guest_name     or "Guest"
        session["guest_category"] = guest_category or ""

        return redirect(url_for("auth.guest_dashboard"))

    # GET — show the optional info form
    return render_template("guest_intro.html")


# =======================================================
# GUEST SKIP (bypasses optional info form)
# =======================================================

@auth.route("/guest/skip")
def guest_skip():

    session["guest_name"]     = "Guest"
    session["guest_category"] = ""

    return redirect(url_for("auth.guest_dashboard"))


# =======================================================
# GUEST DASHBOARD
# =======================================================

@auth.route("/guest/dashboard")
def guest_dashboard():

    return render_template(
        "guest_login.html",
        guest_name=session.get("guest_name", "Guest"),
        guest_category=session.get("guest_category", "")
    )


# =======================================================
# GUEST PROFILE
# =======================================================

@auth.route("/guest/profile", methods=["GET", "POST"])
def guest_profile():

    if request.method == "POST":

        guest_name     = request.form.get("guest_name",     "").strip()
        guest_category = request.form.get("guest_category", "").strip()

        session["guest_name"]     = guest_name     or "Guest"
        session["guest_category"] = guest_category or ""

        flash("Profile updated successfully!", "success")
        return redirect(url_for("auth.guest_profile"))

    return render_template(
        "guest_profile.html",
        guest_name=session.get("guest_name", "Guest"),
        guest_category=session.get("guest_category", "")
    )


# =======================================================
# ADMIN LOGIN
# =======================================================

@auth.route(
    "/admin/login",
    methods=["GET", "POST"]
)
@limiter.limit("5 per minute")
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
            secrets.compare_digest(email, admin_email)
            and secrets.compare_digest(password, admin_password)
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


# =======================================================
# PRIVATE QUEUE API ROUTES (DATABASE persist & privacy)
# =======================================================

def _get_guest_session_key():
    if "guest_session_key" not in session:
        session["guest_session_key"] = f"guest_{secrets.token_hex(16)}"
    return session["guest_session_key"]


def _resolve_guest_key(explicit=None):
    """Resolve the guest identity key.

    Guests do not have a real account, so their request history is grouped under
    an anonymous key. To let a guest recover the same tickets even after logging
    out and back in (which clears the Flask session), the browser persists the
    key in localStorage and sends it back explicitly. This helper prefers the
    explicit (persisted) key and stores it back into the session so it is also
    available on subsequent routine calls.
    """
    if explicit and str(explicit).startswith("guest_"):
        session["guest_session_key"] = str(explicit)
        return str(explicit)
    return _get_guest_session_key()


@auth.route("/api/requests", methods=["GET"])
@limiter.exempt
def get_user_requests():
    student_id = session.get("student_id")

    if student_id:
        requests_query = QueueRequest.query.filter_by(
            student_id=student_id
        ).order_by(QueueRequest.id.desc()).all()
    else:
        guest_key = _resolve_guest_key(request.args.get("guest_key"))
        requests_query = QueueRequest.query.filter_by(
            guest_session_key=guest_key
        ).order_by(QueueRequest.id.desc()).all()

    return jsonify({"success": True, "requests": [r.to_dict() for r in requests_query]})


@auth.route("/api/request/create", methods=["POST"])
def create_queue_request():
    data = request.get_json() or {}

    # Accept either a flat doc (backward compat) or a list of items.
    # items: [{"name": "...", "type": "academic"|"payment", "price": 100}, ...]
    items = data.get("items") or []
    if items and not isinstance(items, list):
        return jsonify({"success": False, "error": "items must be a list"}), 400

    if not items:
        # Backward-compatible single request
        doc_name = (data.get("doc_name", "True Copy Certificate of Registration")).strip()
        service = (data.get("service", "") or "Registrar").strip()
        kind = "payment" if service.lower() in ("cashier", "payment", "assessment") else "academic"
        items = [{"name": doc_name, "type": kind, "price": 100}]

    # Deduplicate identical item names (same doc/payment cannot be selected twice)
    seen = set()
    cleaned = []
    for it in items:
        name = (it.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        is_payment = it.get("type") in ("payment", "cashier") or any(
            p in name.lower() for p in ["tuition", "graduation", "cashier", "assessment"]
        )
        price_raw = it.get("price")
        if price_raw is not None:
            price = int(price_raw)
        else:
            price = 0 if is_payment else 100
        cleaned.append({
            "name": name,
            "type": "payment" if is_payment else "academic",
            "price": price
        })
    items = cleaned

    if not items:
        return jsonify({"success": False, "error": "No items selected"}), 400

    # Determine routing from the item types.
    has_academic = any(it["type"] == "academic" for it in items)
    only_payment = not has_academic

    # ALL requests start at the Cashier queue (C-xxx).
    # Requests with academic items have queue_step="payment" (go to Registrar after).
    # Payment-only requests have queue_step=None (stay at Cashier, no Registrar step).
    cashier_counters = QueueCounter.query.filter(
        QueueCounter.counter_name.like("%Cashier%"),
        QueueCounter.is_active.is_(True)
    ).all()

    if not cashier_counters:
        return jsonify({"success": False, "error": "No active Cashier counter"}), 400

    counter = cashier_counters[0]

    # Ascending queue number for Cashier prefix (C-xxx) using persistent counter
    prefix = counter.now_serving_prefix
    counter.last_number = (counter.last_number or 0) + 1
    num_int = counter.last_number
    queue_number = f"{prefix}-{num_int:03d}"
    db.session.add(counter)

    now = datetime.utcnow()
    tx_id = f"QRS-2026-{now.strftime('%m%d')}-{queue_number}"

    student_id = session.get("student_id")
    guest_key = None if student_id else _resolve_guest_key(data.get("guest_key"))

    summary = ", ".join(it["name"] for it in items)
    total = sum(it["price"] for it in items)
    service_label = "Registrar" if has_academic else "Cashier"
    # All requests pass through the Cashier payment queue first.
    step = "payment"

    new_req = QueueRequest(
        student_id=student_id,
        guest_session_key=guest_key,
        doc_name=summary,
        items=items,
        queue_number=queue_number,
        counter=counter.counter_name,
        service=f"{service_label} – {summary}",
        price=total,
        wait_time="3–5 minutes",
        transaction_id=tx_id,
        status="Processing",
        queue_step=step
    )

    db.session.add(new_req)
    db.session.commit()

    return jsonify({"success": True, "request": new_req.to_dict()})


@auth.route("/api/request/<int:req_id>/complete", methods=["POST"])
def complete_queue_request(req_id):
    req_obj = QueueRequest.query.get(req_id)
    if req_obj:
        req_obj.status = "Completed"
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@auth.route("/api/request/<int:req_id>/cancel", methods=["POST"])
def cancel_queue_request(req_id):
    req_obj = QueueRequest.query.get(req_id)
    if req_obj:
        db.session.delete(req_obj)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


# =======================================================
# PUBLIC TICKET STATUS PAGE
# =======================================================
# Opened when someone scans the QR on their queue ticket.
# No login required — the page simply shows the live status
# of the request identified by its unique transaction ID.

@auth.route("/ticket/<transaction_id>", methods=["GET"])
def ticket_status(transaction_id):
    req_obj = QueueRequest.query.filter_by(transaction_id=transaction_id).first()
    if not req_obj:
        return render_template("ticket_status.html", req=None, found=False), 404
    return render_template("ticket_status.html", req=req_obj, found=True)


# =======================================================
# LIVE QUEUE MONITOR — PUBLIC API
# =======================================================
# Polled every 5 seconds by the Student and Guest dashboards.
# Returns all active counters and the "primary" now-serving ticket.

@auth.route("/api/monitor", methods=["GET"])
@limiter.exempt
def get_monitor():
    counters = QueueCounter.query.filter_by(is_active=True).order_by(QueueCounter.counter_code).all()

    data = [c.to_dict() for c in counters]

    # Primary "Now Serving" = first active counter that is actually serving
    primary = next((c for c in counters if c.now_serving_number > 0), None)
    primary_serving = primary.now_serving if primary else "---"
    primary_counter = primary.counter_name if primary else "No Active Counter"

    return jsonify({
        "success": True,
        "now_serving": primary_serving,
        "primary_counter": primary_counter,
        "counters": data
    })


# =======================================================
# ADMIN COUNTER API — LIST ALL COUNTERS
# =======================================================

@auth.route("/api/admin/counters", methods=["GET"])
@limiter.exempt
def admin_get_counters():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    counters = QueueCounter.query.order_by(QueueCounter.counter_code).all()
    return jsonify({"success": True, "counters": [c.to_dict() for c in counters]})


# =======================================================
# ADMIN COUNTER API — CALL NEXT (LOWEST NUMBER FIRST)
# =======================================================
# Instead of blindly incrementing the "now serving" number,
# Call Next always moves the counter to the LOWEST queue number
# that is still waiting (Processing). This gives the smallest
# number the highest priority and never skips lower tickets.

@auth.route("/api/admin/counter/<int:counter_id>/next", methods=["POST"])
def admin_counter_next(counter_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    counter = db.session.get(QueueCounter, counter_id)
    if not counter:
        return jsonify({"success": False, "error": "Counter not found"}), 404

    prefix = counter.now_serving_prefix

    def _num_of(r):
        m = re.search(rf"{re.escape(prefix)}-(\d+)", r.queue_number or "")
        return int(m.group(1)) if m else 0

    # All tickets still waiting (Processing) OR not-yet-displayed pickups
    # (Ready for pickup) for this counter's prefix. Lowest queue number wins.
    candidates = [
        r for r in QueueRequest.query.filter(
            QueueRequest.queue_number.like(prefix + "-%"),
            QueueRequest.status.in_(["Processing", "Ready for pickup"])
        ).all()
        if _num_of(r) > 0
    ]

    if candidates:
        # Lowest queue number = highest priority.
        next_req = min(candidates, key=_num_of)
        counter.now_serving_number = _num_of(next_req)
        # Keep as "Ready for pickup" so the called number stays displayed
        # on the live counter until the user collects their document.
        next_req.status = "Ready for pickup"

    # If nobody is waiting, leave the now-serving number unchanged.

    counter.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "counter": counter.to_dict()})


# =======================================================
# ADMIN COUNTER API — MANUAL SET NOW SERVING
# =======================================================

@auth.route("/api/admin/counter/<int:counter_id>/set", methods=["POST"])
def admin_counter_set(counter_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    counter = QueueCounter.query.get(counter_id)
    if not counter:
        return jsonify({"success": False, "error": "Counter not found"}), 404

    data = request.get_json() or {}
    new_number = data.get("now_serving_number")
    is_active = data.get("is_active")

    if new_number is not None:
        try:
            counter.now_serving_number = int(new_number)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid number"}), 400

    if is_active is not None:
        counter.is_active = bool(is_active)

    counter.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "counter": counter.to_dict()})


# =======================================================
# ADMIN — RESET ALL COUNTERS & QUEUE
# =======================================================
# Resets every counter's now-serving back to 0 and removes all
# active (Processing / Ready for pickup) requests to start a fresh queue.

@auth.route("/api/admin/reset", methods=["POST"])
def admin_reset():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    for counter in QueueCounter.query.all():
        counter.now_serving_number = 0
        counter.last_number = 0
        counter.updated_at = datetime.utcnow()

    QueueRequest.query.filter(
        QueueRequest.status.in_(["Processing", "Ready for pickup"])
    ).delete(synchronize_session=False)

    db.session.commit()

    return jsonify({"success": True})


# =======================================================
# ADMIN — UPDATE A QUEUE REQUEST STATUS
# =======================================================

@auth.route("/api/admin/request/<int:req_id>/status", methods=["POST"])
def admin_update_request_status(req_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    req_obj = QueueRequest.query.get(req_id)
    if not req_obj:
        return jsonify({"success": False, "error": "Not found"}), 404

    data = request.get_json() or {}
    new_status = data.get("status", "").strip()

    allowed_statuses = {"Processing", "Ready for pickup", "Completed"}
    if new_status not in allowed_statuses:
        return jsonify({"success": False, "error": f"Status must be one of {allowed_statuses}"}), 400

    req_obj.status = new_status
    db.session.commit()

    return jsonify({"success": True, "request": req_obj.to_dict()})


# =======================================================
# ADMIN — CONFIRM PAYMENT (move to Registrar queue)
# =======================================================
# When the Cashier confirms payment for a document request,
# move it from the Cashier queue (C-xxx) to the Registrar
# queue (A-xxx or B-xxx, strictly alternating).

@auth.route("/api/admin/request/<int:req_id>/confirm-payment", methods=["POST"])
def admin_confirm_payment(req_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    req_obj = QueueRequest.query.get(req_id)
    if not req_obj:
        return jsonify({"success": False, "error": "Not found"}), 404

    if req_obj.queue_step != "payment":
        return jsonify({"success": False, "error": "This request is not awaiting payment"}), 400

    # Payment-only request → nothing to route to Registrar, mark completed.
    if not req_obj.has_academic_items:
        req_obj.status = "Completed"
        req_obj.queue_step = None
        req_obj.service = f"Cashier – {req_obj.item_names}"
        db.session.commit()
        return jsonify({"success": True, "request": req_obj.to_dict()})

    # Has academic items → payment done, route to Registrar queue.
    registrar_counters = QueueCounter.query.filter(
        QueueCounter.counter_name.like("%Registrar%"),
        QueueCounter.is_active.is_(True)
    ).order_by(QueueCounter.counter_code).all()

    if not registrar_counters:
        return jsonify({"success": False, "error": "No active Registrar counter"}), 400

    # Strict alternation: A → B → A → B
    alt_a = QueueCounter.query.filter_by(counter_code="A").first()
    last_prefix = alt_a.last_registrar_prefix if alt_a else None
    if last_prefix == "A":
        counter = next(c for c in registrar_counters if c.counter_code == "B")
    else:
        counter = next(c for c in registrar_counters if c.counter_code == "A")

    # Ascending queue number for this Registrar prefix using persistent counter
    prefix = counter.now_serving_prefix
    counter.last_number = (counter.last_number or 0) + 1
    num_int = counter.last_number
    new_queue_number = f"{prefix}-{num_int:03d}"
    db.session.add(counter)

    # Update the request
    req_obj.queue_number = new_queue_number
    req_obj.counter = counter.counter_name
    req_obj.queue_step = "processing"
    req_obj.service = f"Registrar – {req_obj.item_names}"

    # Update alternation state
    if alt_a:
        alt_a.last_registrar_prefix = prefix

    db.session.commit()

    return jsonify({"success": True, "request": req_obj.to_dict()})


# =======================================================
# ADMIN — CANCEL A QUEUE REQUEST
# =======================================================
# Used when a user did not show up in time or took too long.
# Removes the request from the queue so it no longer blocks
# Call Next (which prioritizes the lowest waiting number).

@auth.route("/api/admin/request/<int:req_id>/cancel", methods=["POST"])
def admin_cancel_request(req_id):
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    req_obj = db.session.get(QueueRequest, req_id)
    if not req_obj:
        return jsonify({"success": False, "error": "Not found"}), 404

    db.session.delete(req_obj)
    db.session.commit()

    return jsonify({"success": True})


# =======================================================
# ADMIN — GET ALL QUEUE REQUESTS (FOR MONITOR PANEL)
# =======================================================

@auth.route("/api/admin/requests", methods=["GET"])
@limiter.exempt
def admin_get_requests():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    reqs = QueueRequest.query.order_by(QueueRequest.id.desc()).limit(50).all()
    return jsonify({"success": True, "requests": [r.to_dict() for r in reqs]})
