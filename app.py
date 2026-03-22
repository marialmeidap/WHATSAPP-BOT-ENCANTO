from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# 🔹 VERIFICACIÓN WEBHOOK
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Error", 403

# 🔹 RECIBIR MENSAJES
@app.route("/webhook", methods=["POST"])
def receive():
    data = request.json

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = message["from"]
        text = message["text"]["body"]

        print(f"Mensaje de {from_number}: {text}")

        send_message(from_number, "💖 Hola! Soy Encanto Capilar. ¿En qué puedo ayudarte?")

    except Exception as e:
        print("Error:", e)

    return "ok", 200

# 🔹 ENVIAR MENSAJE
def send_message(to, message):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": message
        }
    }

    response = requests.post(url, headers=headers, json=data)
    print(response.text)

if __name__ == "__main__":
    app.run(port=5000)
