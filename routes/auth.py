"""
===========================================================
QRESERVE
Authentication Routes
===========================================================
"""

from flask import Blueprint, render_template

# Create Blueprint
auth = Blueprint("auth", __name__)


@auth.route("/")
def login():
    """
    Display the Login Page
    """
    return render_template("login.html")


@auth.route("/guest")
def guest():
    """
    Temporary Guest Page
    """
    return "<h2>Guest Dashboard (Coming Soon)</h2>"