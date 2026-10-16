from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Product
from app.utils import admin_required, error, get_json_body, parse_money, parse_non_negative_int

products_bp = Blueprint("products", __name__)

MAX_NAME_LENGTH = 200


def product_to_dict(product):
    return {
        "id": product.id,
        "name": product.name,
        "price": str(product.price),
        "stock": product.stock,
    }


@products_bp.route("/products", methods=["GET"])
def list_products():
    products = db.session.scalars(db.select(Product).order_by(Product.id)).all()
    return jsonify([product_to_dict(p) for p in products]), 200


@products_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return error("Product not found", 404)
    return jsonify(product_to_dict(product)), 200


@products_bp.route("/products", methods=["POST"])
@admin_required
def create_product():
    data = get_json_body()
    if data is None:
        return error("JSON body is required", 400)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME_LENGTH:
        return error(f"'name' must be a non-empty string of at most {MAX_NAME_LENGTH} characters", 400)

    price = parse_money(data.get("price"))
    if price is None:
        return error("'price' must be a positive amount with at most 2 decimal places", 400)

    stock = parse_non_negative_int(data.get("stock"))
    if stock is None:
        return error("'stock' must be a non-negative integer", 400)

    product = Product(name=name.strip(), price=price, stock=stock)
    db.session.add(product)
    db.session.commit()

    return jsonify(product_to_dict(product)), 201