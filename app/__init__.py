from flask import Flask

from app.config import Config
from app.extensions import db, jwt
from app.utils import error


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)
    register_jwt_errors()

    from app import models  # registers models with SQLAlchemy
    from app.routes.auth import auth_bp
    from app.routes.health import health_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)

    return app


def register_jwt_errors():
    @jwt.unauthorized_loader
    def missing_token(reason):
        return error("Missing or malformed Authorization header", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error("Invalid token", 401)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error("Token has expired", 401)