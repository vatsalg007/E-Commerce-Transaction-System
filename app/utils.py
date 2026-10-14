from flask import jsonify


def error(message, status):
    return jsonify({"error": message}), status