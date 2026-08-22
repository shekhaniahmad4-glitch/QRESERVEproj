"""
===========================================================
QRESERVE
Database Models
===========================================================
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


# -------------------------------------------------------
# Database Object
# -------------------------------------------------------

db = SQLAlchemy()


# -------------------------------------------------------
# Student Model
# -------------------------------------------------------

class Student(db.Model):

    __tablename__ = "students"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    def __repr__(self):

        return f"<Student {self.email}>"

