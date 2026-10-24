from flask import Blueprint, jsonify

from app.openapi import SPEC

docs_bp = Blueprint("docs", __name__)

SWAGGER_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>E-Commerce API docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({url: "/openapi.json", dom_id: "#swagger-ui", persistAuthorization: true});
  </script>
</body>
</html>"""


@docs_bp.route("/openapi.json", methods=["GET"])
def openapi_spec():
    return jsonify(SPEC)


@docs_bp.route("/docs", methods=["GET"])
def swagger_ui():
    return SWAGGER_PAGE