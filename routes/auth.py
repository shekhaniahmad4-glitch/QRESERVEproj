from flask import Blueprint, render_template

auth = Blueprint("auth", __name__)


@auth.route("/")
@auth.route("/login")
def login():
    """
    Display the Login Page
    """
    return render_template("login.html")


@auth.route("/signup")
def signup():
    return render_template("sign_up.html")


@auth.route("/guest")
def guest():
    return "<h2>Guest Dashboard (Coming Soon)</h2>"