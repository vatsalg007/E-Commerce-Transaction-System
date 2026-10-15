import re

import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.utils import error

auth_bp = Blueprint("auth", __name__)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt only accepts up to 72 bytes


def read_credentials():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, None

    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return None, None

    return email.strip().lower(), password


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    email, password = read_credentials()
    if email is None:
        return error("JSON body with string 'email' and 'password' is required", 400)
    if not EMAIL_PATTERN.fullmatch(email):
        return error("Invalid email format", 400)
    if len(password) < MIN_PASSWORD_LENGTH:
        return error(f"Password must be at least {MIN_PASSWORD_LENGTH} characters", 400)
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return error("Password is too long", 400)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user = User(email=email, password_hash=password_hash.decode("utf-8"))
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("Email already registered", 409)

    return jsonify({"id": user.id, "email": user.email}), 201


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    email, password = read_credentials()
    if email is None:
        return error("JSON body with string 'email' and 'password' is required", 400)

    user = db.session.scalars(db.select(User).where(User.email == email)).first()
    password_bytes = password.encode("utf-8")

    if (
        user is None
        or len(password_bytes) > MAX_PASSWORD_BYTES
        or not bcrypt.checkpw(password_bytes, user.password_hash.encode("utf-8"))
    ):
        return error("Invalid email or password", 401)

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token}), 200


@auth_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return error("User not found", 404)

    return jsonify({
        "id": user.id,
        "email": user.email,
        "wallet_balance": str(user.wallet_balance),
        "is_admin": user.is_admin,
    }), 200