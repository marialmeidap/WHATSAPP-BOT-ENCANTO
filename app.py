from flask import Flask, request
import requests
import os
import time

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

GRAPH_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

# MVP: memoria en proceso. Si Render reinicia, se borra.
responded_users = set()

ORGANIC_KEYWORDS = [
    "hola", "buenas", "ola", "info", "información", "precio", "buen dia",
    "buen día", "disponible", "tienes", "me interesa", "buenas tardes",
    "buenas noches"
]

TEXT_6_MONAS = """✨ EXTENSIONES PREMIUM ✨
💁🏽‍♀️ Disponibles LISSAS, CRESPAS Y LOOSE WAVE
💎 Fibra 100% orgánica – seminaturales
✨ Suaves, con brillo, no se enredan
🔥 Se pueden LAVAR y PLANCHAR

🔥 PRECIO: $70.000  x paquete *COMPLETO*🔥
🏍️ Domicilio en Cali: $10.000
🚚 Envío resto del país: $30.000 (paga al recibir)

📍 Cali – Carrera 7 #11-31 Oficina 402

💖 *Transforma tu Belleza*"""

TEXT_CLIP = """✨ EXTENSIONES SEMI NATURALES CLIP ✨

💇‍♀️ Cortina con 5 clips
📏 30 cm x 60 cm
🔥 Aptas para lavar y planchar
🌟 Fibra semi natural con apariencia natural
⚡ Se colocan en menos de 1 minuto

💰 PROMO
⭐ 1 por $30.000
⭐ 2 por $50.000

📍 Estamos en Cali
🚚 Domicilio en Cali: $10.000
📦 Envío nacional contraentrega
(Pagas al recibir valor de las extensiones + costo del envío)."""

ASK_CITY = "¿En qué ciudad te encuentras?"

IMAGES_LISAS = [
    "1565319357882743",
    "937334182234863",
    "1244649211209174",
    "26384617747894999",
    "954661733637705",
    "1428189008608703",
    "907729562023318",
    "1456494535880271",
    "1561714538234849",
    "1973058493636797",
    "1432680811161272"
]

IMAGES_CRESPAS = [
    "828484266181382",
    "1443981077222345",
    "1499484381693564",
    "1468342111360744",
    "911971131810964",
    "768863612726703"
]

IMAGES_ONDULADAS = [
    "https://drive.google.com/uc?export=view&id=1OuhhYQJ4Q_lnIkW9cdIsOh6AqMwaEHYx",
    "https://drive.google.com/uc?export=view&id=1U8MIdrZFh1HkLHRfyyySEG7FMYMW-hdk",
    "https://drive.google.com/uc?export=view&id=1F9B3G_HzQ93TWVdHaApzJRl9e8G-maw1",
    "https://drive.google.com/uc?export=view&id=1ah9yOhfujcQHazGs6hze32C9dUBIGJ9q"
]

IMAGES_CLIP = [
    "https://drive.google.com/uc?export=view&id=1MWV76NbvUpOfSNF3tVvGL4WpUq-q8dCa",
    "https://drive.google.com/uc?export=view&id=1HrSpgC4Mj-f5eY1G2Aze50l8lDCNcA52",
    "https://drive.google.com/uc?export=view&id=1XuUlh641_Oqlu5OkI13CqCeRGrSqkILN",
    "https://drive.google.com/uc?export=view&id=1bWXry_6PWg7AVI7pNt43KVqjFiZayrOK",
    "https://drive.google.com/uc?export=view&id=14-q-vFvt07alg5SKLlJ18VgaZAECefgi",
    "https://drive.google.com/uc?export=view&id=19pYapMt3i00FmsrE02FIFl7DLtkfMk_i",
    "https://drive.google.com/uc?export=view&id=1b84EKpLdnjUSLvyPfrYZstQP_xdpSDCy",
    "https://drive.google.com/uc?export=view&id=1GOyEYY1RAGGEX3kwrmGAVqg4q8aYzsXm",
    "https://drive.google.com/uc?export=view&id=1-HJmhlk0ykg09xqi7Xcm3hpX12YvWgVD"
]

AD_PRODUCT_MAP = {
    "6_monas": "6_monas",
    "6 monas": "6_monas",
    "extension 6 moñas": "6_monas",
    "clip": "clip",
    "instala facil": "clip",
    "instala fácil": "clip",
    "clip instala facil": "clip",
    "clip instala fácil": "clip",
}

def send_text(to, body):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    response = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("TEXT:", response.status_code, response.text)

def send_image(to, image_value):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # Si son solo números, asumimos media_id de Meta
    if str(image_value).isdigit():
        image_data = {"id": image_value}
    else:
        image_data = {"link": image_value}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_data,
    }

    response = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("IMAGE:", response.status_code, response.text)

def normalize_text(text):
    return (text or "").strip().lower()

def is_organic_message(text):
    text = normalize_text(text)
    if not text:
        return True
    return any(keyword in text for keyword in ORGANIC_KEYWORDS)

def get_message_text(message):
    if message.get("type") == "text":
        return message.get("text", {}).get("body", "")
    return ""

def detect_ad_product(message, value):
    candidates = []
    context = message.get("context", {})
    referral = message.get("referral", {})

    for obj in [context, referral, value]:
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str):
                    candidates.append(v.lower())

    joined = " | ".join(candidates)

    for key, product in AD_PRODUCT_MAP.items():
        if key in joined:
            return product

    return None

def send_flow_6_monas(to):
    send_text(to, TEXT_6_MONAS)
    time.sleep(2)

    if IMAGES_LISAS:
        send_image(to, IMAGES_LISAS[0], "*EXTENSIONES LISAS*")
        time.sleep(1.5)

        for url in IMAGES_LISAS[1:]:
            send_image(to, url)
            time.sleep(1.2)

    time.sleep(3)

    if IMAGES_CRESPAS:
        send_image(to, IMAGES_CRESPAS[0], "*EXTENSIONES CRESPAS*")
        time.sleep(1.5)

        for url in IMAGES_CRESPAS[1:]:
            send_image(to, url)
            time.sleep(1.2)

    time.sleep(3)

    if IMAGES_ONDULADAS:
        send_image(to, IMAGES_ONDULADAS[0], "*EXTENSIONES ONDULADAS*")
        time.sleep(1.5)

        for url in IMAGES_ONDULADAS[1:]:
            send_image(to, url)
            time.sleep(1.2)

    time.sleep(2)
    send_text(to, ASK_CITY)

def send_flow_clip(to):
    send_text(to, TEXT_CLIP)
    time.sleep(2)

    if IMAGES_CLIP:
        send_image(to, IMAGES_CLIP[0], "*EXTENSIONES CLIP*")
        time.sleep(1.5)

        for url in IMAGES_CLIP[1:]:
            send_image(to, url)
            time.sleep(1.2)

    time.sleep(2)
    send_text(to, ASK_CITY)

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
    print("Webhook recibido:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return "ok", 200

        message = value["messages"][0]
        from_number = message["from"]

        if from_number in responded_users:
            print(f"{from_number} ya recibió respuesta inicial. No responder.")
            return "ok", 200

        text = get_message_text(message)
        ad_product = detect_ad_product(message, value)

        print("Número:", from_number)
        print("Texto:", text)
        print("Producto detectado por anuncio:", ad_product)

        if ad_product == "6_monas":
            send_flow_6_monas(from_number)
            responded_users.add(from_number)
            return "ok", 200

        if ad_product == "clip":
            send_flow_clip(from_number)
            responded_users.add(from_number)
            return "ok", 200

        if is_organic_message(text):
            send_flow_6_monas(from_number)
            responded_users.add(from_number)
            return "ok", 200

        send_flow_6_monas(from_number)
        responded_users.add(from_number)

    except Exception as e:
        print("Error procesando mensaje:", e)

    return "ok", 200

if __name__ == "__main__":
    app.run(port=5000)
