from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"

@app.route("/", methods=["GET"])
def home():
    return "Bot activo", 200

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Error", 403

@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json()
    print("Mensaje recibido:", data)
    return "ok", 200

if __name__ == "__main__":
    app.run(port=5000)
