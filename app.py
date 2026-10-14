from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True)

    if data is None or "name" not in data:
        return jsonify({"error": "JSON body with 'name' is required"}), 400

    return jsonify({"message": f"Hello, {data['name']}"}), 200


if __name__ == "__main__":
    app.run(debug=True)