from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Error de verificación"

@app.route("/webhook", methods=["POST"])
def receive():
    data = request.json
    print("Mensaje recibido:", data)
    return "ok", 200

if __name__ == "__main__":
    app.run(port=5000)
