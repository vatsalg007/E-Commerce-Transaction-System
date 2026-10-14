from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db
from app.utils import error

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return error("Database unavailable", 503)
    return jsonify({"status": "ok", "database": "connected"}), 200