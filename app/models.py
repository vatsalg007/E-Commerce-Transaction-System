from sqlalchemy import CheckConstraint, UniqueConstraint

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("wallet_balance >= 0", name="ck_users_wallet_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    wallet_balance = db.Column(db.Numeric(12, 2), nullable=False, server_default="0")
    is_admin = db.Column(db.Boolean, nullable=False, server_default="false")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    items = db.relationship("OrderItem", backref="order")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)

    product = db.relationship("Product")


class IdempotencyKey(db.Model):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_idempotency_keys_user_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    idempotency_key = db.Column(db.String(36), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    response_code = db.Column(db.Integer)  # filled in before the transaction commits
    response_body = db.Column(db.JSON)  # filled in before the transaction commits
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())