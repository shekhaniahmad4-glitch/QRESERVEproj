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


# -------------------------------------------------------
# Student Profile Model
# -------------------------------------------------------

class StudentProfile(db.Model):

    __tablename__ = "student_profiles"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    full_name = db.Column(
        db.String(150),
        nullable=True
    )

    age = db.Column(
        db.Integer,
        nullable=True
    )

    course = db.Column(
        db.String(150),
        nullable=True
    )

    year_level = db.Column(
        db.String(20),
        nullable=True
    )

    section = db.Column(
        db.String(50),
        nullable=True
    )

    profile_pic = db.Column(
        db.String(255),
        nullable=True
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    student = db.relationship(
        "Student",
        backref=db.backref("profile", uselist=False, cascade="all, delete-orphan")
    )

    def __repr__(self):

        return f"<StudentProfile student_id={self.student_id}>"

