from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Order, OrderItem

orders_bp = Blueprint("orders", __name__)


def order_to_dict(order):
    return {
        "order_id": order.id,
        "total_amount": str(order.total_amount),
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
            }
            for item in order.items
        ],
    }


@orders_bp.route("/orders", methods=["GET"])
@jwt_required()
def list_orders():
    orders = db.session.scalars(
        db.select(Order)
        .where(Order.user_id == int(get_jwt_identity()))
        .options(selectinload(Order.items).selectinload(OrderItem.product))  # avoids N+1 queries
        .order_by(Order.created_at.desc(), Order.id.desc())
    ).all()

    return jsonify([order_to_dict(o) for o in orders]), 200