"""OpenAPI description of the API, served at /openapi.json and rendered by Swagger UI at /docs."""


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def json_body(schema):
    return {"required": True, "content": {"application/json": {"schema": schema}}}


def json_response(description, schema):
    return {"description": description, "content": {"application/json": {"schema": schema}}}


def error_response(description):
    return json_response(description, ref("Error"))


SECURED = [{"bearerAuth": []}]

SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "E-Commerce Transaction API",
        "version": "1.0.0",
        "description": (
            "Register and log in, then click Authorize and paste the access token. "
            "Checkout needs a new UUID in the Idempotency-Key header for every purchase attempt."
        ),
    },
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}},
        "schemas": {
            "Error": {"type": "object", "properties": {"error": {"type": "string"}}},
            "Credentials": {
                "type": "object",
                "required": ["email", "password"],
                "properties": {
                    "email": {"type": "string", "example": "buyer@example.com"},
                    "password": {"type": "string", "minLength": 8, "example": "secret123"},
                },
            },
            "RegisteredUser": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "email": {"type": "string"}},
            },
            "Token": {"type": "object", "properties": {"access_token": {"type": "string"}}},
            "Me": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string"},
                    "wallet_balance": {"type": "string", "example": "500.00"},
                    "is_admin": {"type": "boolean"},
                },
            },
            "Balance": {"type": "object", "properties": {"wallet_balance": {"type": "string", "example": "500.00"}}},
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "price": {"type": "string", "example": "499.00"},
                    "stock": {"type": "integer"},
                },
            },
            "NewProduct": {
                "type": "object",
                "required": ["name", "price", "stock"],
                "properties": {
                    "name": {"type": "string", "example": "Wireless Mouse"},
                    "price": {"type": "string", "example": "499.00"},
                    "stock": {"type": "integer", "example": 10},
                },
            },
            "TopUp": {
                "type": "object",
                "required": ["amount"],
                "properties": {"amount": {"type": "string", "example": "500.00"}},
            },
            "CheckoutRequest": {
                "type": "object",
                "required": ["items", "expected_total"],
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["product_id", "quantity"],
                            "properties": {
                                "product_id": {"type": "integer"},
                                "quantity": {"type": "integer", "example": 1},
                            },
                        },
                    },
                    "expected_total": {"type": "string", "example": "499.00"},
                },
            },
            "Order": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "total_amount": {"type": "string"},
                    "created_at": {"type": "string"},
                    "wallet_balance": {"type": "string", "description": "Only in the checkout response"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "integer"},
                                "product_name": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
    "paths": {
        "/health": {
            "get": {
                "tags": ["System"],
                "summary": "Service and database status",
                "responses": {"200": {"description": "Healthy"}, "503": error_response("Database unavailable")},
            }
        },
        "/auth/register": {
            "post": {
                "tags": ["Auth"],
                "summary": "Create an account",
                "requestBody": json_body(ref("Credentials")),
                "responses": {
                    "201": json_response("Account created", ref("RegisteredUser")),
                    "400": error_response("Invalid input"),
                    "409": error_response("Email already registered"),
                },
            }
        },
        "/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Log in and receive a JWT (valid for 1 hour)",
                "requestBody": json_body(ref("Credentials")),
                "responses": {
                    "200": json_response("Logged in", ref("Token")),
                    "400": error_response("Invalid input"),
                    "401": error_response("Invalid email or password"),
                },
            }
        },
        "/auth/me": {
            "get": {
                "tags": ["Auth"],
                "summary": "Current user and wallet balance",
                "security": SECURED,
                "responses": {
                    "200": json_response("Current user", ref("Me")),
                    "401": error_response("Missing, invalid or expired token"),
                },
            }
        },
        "/products": {
            "get": {
                "tags": ["Products"],
                "summary": "List products",
                "responses": {"200": json_response("All products", {"type": "array", "items": ref("Product")})},
            },
            "post": {
                "tags": ["Products"],
                "summary": "Create a product (admin only)",
                "security": SECURED,
                "requestBody": json_body(ref("NewProduct")),
                "responses": {
                    "201": json_response("Product created", ref("Product")),
                    "400": error_response("Invalid input"),
                    "401": error_response("Missing, invalid or expired token"),
                    "403": error_response("Admin access required"),
                },
            },
        },
        "/products/{product_id}": {
            "get": {
                "tags": ["Products"],
                "summary": "Get one product",
                "parameters": [
                    {"name": "product_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": json_response("The product", ref("Product")),
                    "404": error_response("Product not found"),
                },
            }
        },
        "/wallet/topup": {
            "post": {
                "tags": ["Wallet"],
                "summary": "Add money to the wallet",
                "security": SECURED,
                "requestBody": json_body(ref("TopUp")),
                "responses": {
                    "200": json_response("New balance", ref("Balance")),
                    "400": error_response("Invalid amount"),
                    "401": error_response("Missing, invalid or expired token"),
                },
            }
        },
        "/checkout": {
            "post": {
                "tags": ["Orders"],
                "summary": "Place an order (idempotent)",
                "security": SECURED,
                "parameters": [
                    {
                        "name": "Idempotency-Key",
                        "in": "header",
                        "required": True,
                        "description": "A UUID, new for each purchase attempt. Resend the same one only to retry.",
                        "schema": {"type": "string", "format": "uuid"},
                    }
                ],
                "requestBody": json_body(ref("CheckoutRequest")),
                "responses": {
                    "201": json_response("Order created, or the stored response replayed", ref("Order")),
                    "400": error_response("Invalid cart, total or Idempotency-Key"),
                    "401": error_response("Missing, invalid or expired token"),
                    "404": error_response("Product not found"),
                    "409": error_response("Insufficient stock, price changed or insufficient wallet balance"),
                    "422": error_response("Idempotency-Key already used with a different request"),
                },
            }
        },
        "/orders": {
            "get": {
                "tags": ["Orders"],
                "summary": "Your order history, newest first",
                "security": SECURED,
                "responses": {
                    "200": json_response("Orders", {"type": "array", "items": ref("Order")}),
                    "401": error_response("Missing, invalid or expired token"),
                },
            }
        },
    },
}