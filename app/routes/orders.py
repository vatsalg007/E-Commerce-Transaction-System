import uuid
from decimal import Decimal

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Order, OrderItem, Product, User
from app.utils import error, get_json_body, parse_money, parse_positive_int

orders_bp = Blueprint("orders", __name__)

MAX_LINES_PER_ORDER = 20
MAX_QUANTITY_PER_PRODUCT = 100


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


def parse_cart(data):
    """Return {product_id: quantity} with duplicates merged, or None if invalid."""
    items = data.get("items")
    if not isinstance(items, list) or not items or len(items) > MAX_LINES_PER_ORDER:
        return None

    cart = {}
    for line in items:
        if not isinstance(line, dict):
            return None
        product_id = parse_positive_int(line.get("product_id"))
        quantity = parse_positive_int(line.get("quantity"))
        if product_id is None or quantity is None:
            return None
        cart[product_id] = cart.get(product_id, 0) + quantity
        if cart[product_id] > MAX_QUANTITY_PER_PRODUCT:
            return None
    return cart


@orders_bp.route("/checkout", methods=["POST"])
@jwt_required()
def checkout():
    data = get_json_body()
    if data is None:
        return error("JSON body is required", 400)

    cart = parse_cart(data)
    if cart is None:
        return error(
            f"'items' must be a list of 1-{MAX_LINES_PER_ORDER} entries, each with a positive integer "
            f"'product_id' and 'quantity' (at most {MAX_QUANTITY_PER_PRODUCT} per product)",
            400,
        )

    expected_total = parse_money(data.get("expected_total"))
    if expected_total is None:
        return error("'expected_total' must be a positive amount with at most 2 decimal places", 400)

    user_id = int(get_jwt_identity())
    total = Decimal("0")
    lines = []

    # 1. Reserve stock. Sorted ids: every checkout locks rows in the same order, so no deadlocks.
    for product_id in sorted(cart):
        quantity = cart[product_id]
        price = db.session.execute(
            db.update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)  # the guard
            .values(stock=Product.stock - quantity)
            .returning(Product.price)
        ).scalar_one_or_none()

        if price is None:
            db.session.rollback()  # undo any stock already reserved
            if db.session.get(Product, product_id) is None:
                return error(f"Product {product_id} not found", 404)
            return error(f"Insufficient stock for product {product_id}", 409)

        total += price * quantity
        lines.append((product_id, quantity, price))

    # 2. Confirm the price the user saw. The rows are still locked, so prices cannot change before commit.
    if total != expected_total:
        db.session.rollback()  # releases the reserved stock
        return error("Price changed", 409, current_total=str(total))

    # 3. Charge the wallet with the same guard pattern.
    new_balance = db.session.execute(
        db.update(User)
        .where(User.id == user_id, User.wallet_balance >= total)
        .values(wallet_balance=User.wallet_balance - total)
        .returning(User.wallet_balance)
    ).scalar_one_or_none()

    if new_balance is None:
        db.session.rollback()  # also releases the stock reserved above
        return error("Insufficient wallet balance", 409)

    # 4. Record the order and its items at the prices just read.
    order = Order(
        user_id=user_id,
        total_amount=total,
        idempotency_key=str(uuid.uuid4()),  # placeholder until Phase 10
    )
    db.session.add(order)
    for product_id, quantity, price in lines:
        db.session.add(OrderItem(order=order, product_id=product_id, quantity=quantity, unit_price=price))

    # 5. One commit: everything above becomes permanent together.
    db.session.commit()

    response = order_to_dict(order)
    response["wallet_balance"] = str(new_balance)
    return jsonify(response), 201

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