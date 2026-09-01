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

import os
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
from werkzeug.utils import secure_filename

from database import db, Student, StudentProfile

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
