from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User

MAX_MONEY = Decimal("100000.00")


def error(message, status, **extra):
    return jsonify({"error": message, **extra}), status


def get_json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


def parse_money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_MONEY:
        return None
    if amount.as_tuple().exponent < -2:  # more than 2 decimal places
        return None
    return amount


def parse_non_negative_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return error("User no longer exists", 401)
        if not user.is_admin:
            return error("Admin access required", 403)
        return fn(*args, **kwargs)

    return wrapper



def parse_positive_int(value):
    number = parse_non_negative_int(value)
    if number is None or number == 0:
        return None
    return number