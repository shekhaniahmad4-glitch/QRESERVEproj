from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

auth = Blueprint("auth", __name__)


# =========================================================
# STUDENT LOGIN
# =========================================================

@auth.route("/")
@auth.route("/login")
def login():
    """
    Display the Student Login Page
    """
    return render_template("login.html")


# =========================================================
# SIGN UP
# =========================================================

@auth.route("/signup")
def signup():
    """
    Display the Student Sign Up Page
    """
    return render_template("sign_up.html")


# =========================================================
# GUEST
# =========================================================

@auth.route("/guest")
def guest():
    """
    Display Guest Dashboard
    """
    return render_template("guest_login.html")


# =========================================================
# ADMIN LOGIN
# =========================================================

@auth.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    error = None

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Admin credentials from config.py
        admin_email = current_app.config["ADMIN_EMAIL"]
        admin_password = current_app.config["ADMIN_PASSWORD"]

        # Check credentials
        if email == admin_email and password == admin_password:

            # Create admin session
            session["admin_logged_in"] = True
            session["admin_email"] = email

            return redirect(url_for("auth.admin_dashboard"))

        else:
            error = "Invalid administrator email or password."

    return render_template(
        "admin_login.html",
        error=error
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@auth.route("/admin/dashboard")
def admin_dashboard():

    # Prevent unauthorized access
    if not session.get("admin_logged_in"):
        return redirect(url_for("auth.admin_login"))

    return render_template("admin_dashboard.html")


# =========================================================
# ADMIN LOGOUT
# =========================================================

@auth.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)
    session.pop("admin_email", None)

    return redirect(url_for("auth.admin_login"))