from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User
from app.utils import MAX_MONEY, error, get_json_body, parse_money

wallet_bp = Blueprint("wallet", __name__)


@wallet_bp.route("/wallet/topup", methods=["POST"])
@jwt_required()
def topup():
    data = get_json_body()
    if data is None:
        return error("JSON body is required", 400)

    amount = parse_money(data.get("amount"))
    if amount is None:
        return error(f"'amount' must be positive, at most {MAX_MONEY}, with at most 2 decimal places", 400)

    # Atomic: the database adds to the current balance in one statement
    stmt = (
        db.update(User)
        .where(User.id == int(get_jwt_identity()))
        .values(wallet_balance=User.wallet_balance + amount)
        .returning(User.wallet_balance)
    )
    new_balance = db.session.execute(stmt).scalar_one_or_none()

    if new_balance is None:
        db.session.rollback()
        return error("User no longer exists", 401)

    db.session.commit()
    return jsonify({"wallet_balance": str(new_balance)}), 200