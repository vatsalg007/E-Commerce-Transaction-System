
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import IdempotencyKey, Order, OrderItem, Product, User
from app.utils import (
    error,
    get_json_body,
    parse_idempotency_key,
    parse_money,
    parse_positive_int,
    request_fingerprint,
)

orders_bp = Blueprint("orders", __name__)

MAX_LINES_PER_ORDER = 20
MAX_QUANTITY_PER_PRODUCT = 100


class CheckoutRejected(Exception):
    """A definitive business failure (stock, price, wallet). Its response is stored under the key."""

    def __init__(self, status, body):
        self.status = status
        self.body = body


def json_response(body, status, replayed=False):
    response = jsonify(body)
    response.status_code = status
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return response


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


def replay(user_id, idempotency_key, fingerprint):
    """Return the stored response for this key, or a 422 if the request differs."""
    record = db.session.scalars(
        db.select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    ).one()

    if record.request_hash != fingerprint:
        return error("Idempotency-Key was already used with a different request", 422)

    return json_response(record.response_body, record.response_code, replayed=True)


def execute_checkout(user_id, cart, expected_total):
    """Reserve stock, confirm the price, charge the wallet and create the order.

    Returns the response body. Raises CheckoutRejected on a definitive failure.
    """
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
            if db.session.get(Product, product_id) is None:
                raise CheckoutRejected(404, {"error": f"Product {product_id} not found"})
            raise CheckoutRejected(409, {"error": f"Insufficient stock for product {product_id}"})

        total += price * quantity
        lines.append((product_id, quantity, price))

    # 2. Confirm the price the user saw. The rows are still locked, so prices cannot change before commit.
    if total != expected_total:
        raise CheckoutRejected(409, {"error": "Price changed", "current_total": str(total)})

    # 3. Charge the wallet with the same guard pattern.
    new_balance = db.session.execute(
        db.update(User)
        .where(User.id == user_id, User.wallet_balance >= total)
        .values(wallet_balance=User.wallet_balance - total)
        .returning(User.wallet_balance)
    ).scalar_one_or_none()

    if new_balance is None:
        raise CheckoutRejected(409, {"error": "Insufficient wallet balance"})

    # 4. Record the order and its items at the prices just read.
    order = Order(user_id=user_id, total_amount=total)
    db.session.add(order)
    for product_id, quantity, price in lines:
        db.session.add(OrderItem(order=order, product_id=product_id, quantity=quantity, unit_price=price))
    db.session.flush()

    body = order_to_dict(order)
    body["wallet_balance"] = str(new_balance)
    return body


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

    idempotency_key = parse_idempotency_key(request.headers.get("Idempotency-Key"))
    if idempotency_key is None:
        return error("'Idempotency-Key' header with a valid UUID is required", 400)

    user_id = int(get_jwt_identity())
    fingerprint = request_fingerprint(cart, expected_total)

    # 0. Claim the key. A concurrent request with the same key waits here until this
    #    transaction commits or rolls back, so only one request can proceed.
    key_id = db.session.execute(
        pg_insert(IdempotencyKey)
        .values(user_id=user_id, idempotency_key=idempotency_key, request_hash=fingerprint)
        .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
        .returning(IdempotencyKey.id)
    ).scalar_one_or_none()

    if key_id is None:  # key already used by a committed request
        db.session.rollback()  # ends the empty transaction
        return replay(user_id, idempotency_key, fingerprint)

    # 1-4. The work runs inside a savepoint. A definitive failure rolls back to it, which undoes
    #      stock and wallet changes but keeps the key row. Any other exception is a transient
    #      failure: it propagates, and the whole transaction, including the claim, is rolled back.
    try:
        with db.session.begin_nested():
            body = execute_checkout(user_id, cart, expected_total)
        status = 201
    except CheckoutRejected as rejection:
        status, body = rejection.status, rejection.body


    # 5. Store the outcome on the key and commit once: claim, outcome and (on success) stock,
    #    wallet, order and items become permanent together.
    record = db.session.get(IdempotencyKey, key_id)
    record.response_code = status
    record.response_body = body
    db.session.commit()

    return json_response(body, status)


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