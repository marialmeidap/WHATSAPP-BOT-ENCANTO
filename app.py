from flask import Flask, request
import requests
import os
import time
import threading
import queue

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"
ACCESS_TOKEN = os.getenv("EAAR9UMSKSuYBRMF8IaJuLIEwJpkAdOEAEpsgZBsju6QEq4bfkmhTjcgdVbNUVCPI4E8mhAT4yf7zZA2xtFZACHnzNorexlAf4nqHPUOPZA0ETKzakDmirvYBUAINm58NHJf9tCzDY8KAG74hjRXE6zlmC0LO5caWQeEzfWwstWkc0uahnYTZBZBpr8MfgwaB96D1ZCfT2SaTajywbZA8LZBklc3E7ZACqwhFiGhttWnAqRs8glPACdZB0Npci12eNNEZAiFpsKZCDHk1MFTAtM0nYOLTK")
PHONE_NUMBER_ID = os.getenv("1035347582995035")

GRAPH_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

# ===== Estado en memoria =====
processed_message_ids = set()
responded_users = set()
processing_users = set()
job_queue = queue.Queue()

ORGANIC_KEYWORDS = [
    "hola", "buenas", "ola", "info", "información", "precio", "buen dia",
    "buen día", "disponible", "tienes", "me interesa", "buenas tardes",
    "buenas noches", ".", "ok"
]

TEXT_6_MONAS = """✨ EXTENSIONES PREMIUM ✨
💁🏽‍♀️ Disponibles LISSAS, CRESPAS Y LOOSE WAVE
💎 Fibra 100% orgánica – seminaturales
✨ Suaves, con brillo, no se enredan
🔥 Se pueden LAVAR y PLANCHAR

🔥 PRECIO: $70.000 x paquete *COMPLETO* 🔥
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
    "1273230737597278",
    "912074648403700",
    "1881908755787004",
    "1512115730913887"
]

IMAGES_CLIP = [
    "1464591795317429",
    "1460397305827405",
    "1457464749426706",
    "1471791208017752",
    "1465807678319486",
    "2012295003036663",
    "2445441919220843",
    "2212782709547264",
    "824009070011832"
]

# Reemplaza estos IDs cuando tengas los reales
AD_ID_MAP = {
    # "123456789012345": "clip",
    # "987654321098765": "6_monas",
}

def send_text(to, body):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(to),
        "type": "text",
        "text": {"body": body},
    }
    r = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("TEXT:", r.status_code, r.text)
    return r

def send_image(to, media_id):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(to),
        "type": "image",
        "image": {"id": str(media_id)},
    }
    r = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("IMAGE:", r.status_code, r.text)
    return r

def normalize_text(text):
    return (text or "").strip().lower()

def is_organic_message(text):
    text = normalize_text(text)
    if not text:
        return True
    return any(k in text for k in ORGANIC_KEYWORDS)

def get_message_text(message):
    if message.get("type") == "text":
        return message.get("text", {}).get("body", "")
    return ""

def detect_ad_product(message, value):
    # 1) si logras extraer ad_id exacto del webhook
    possible_ids = []

    referral = message.get("referral", {})
    context = message.get("context", {})

    for obj in [referral, context, value]:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    if v in AD_ID_MAP:
                        return AD_ID_MAP[v]
                    possible_ids.append(v)

    # 2) fallback temporal: si vino de anuncio y solo tienes clip activo
    blob = str(value).lower()
    if "referral" in blob or "ctwa" in blob:
        return "clip"

    return None

def send_chunked_images(to, images, first_chunk, second_chunk=None, pause_between_chunks=2):
    for media_id in images[0:first_chunk]:
        send_image(to, media_id)
        time.sleep(1)

    if second_chunk is not None and len(images) > first_chunk:
        time.sleep(pause_between_chunks)
        for media_id in images[first_chunk:second_chunk]:
            send_image(to, media_id)
            time.sleep(1)

def send_flow_6_monas(to):
    send_text(to, TEXT_6_MONAS)
    time.sleep(1.5)

    send_text(to, "✨ EXTENSIONES LISAS DISPONIBLES")
    time.sleep(1)
    send_chunked_images(to, IMAGES_LISAS, first_chunk=5, second_chunk=11, pause_between_chunks=2)

    time.sleep(2)
    send_text(to, "🔥 EXTENSIONES CRESPAS (FULL VOLUMEN)")
    time.sleep(1)
    send_chunked_images(to, IMAGES_CRESPAS, first_chunk=3, second_chunk=6, pause_between_chunks=2)

    time.sleep(2)
    send_text(to, "🌊 LOOSE WAVE (ONDULADAS NATURALES)")
    time.sleep(1)
    send_chunked_images(to, IMAGES_ONDULADAS, first_chunk=4, second_chunk=None, pause_between_chunks=2)

    time.sleep(2)
    send_text(to, ASK_CITY)

def send_flow_clip(to):
    send_text(to, TEXT_CLIP)
    time.sleep(1.5)

    send_text(to, "*EXTENSIONES CLIP*")
    time.sleep(1)
    send_chunked_images(to, IMAGES_CLIP, first_chunk=5, second_chunk=9, pause_between_chunks=2)

    time.sleep(2)
    send_text(to, ASK_CITY)

def process_job(job):
    from_number = job["from_number"]
    text = job["text"]
    ad_product = job["ad_product"]

    try:
        print("PROCESSING JOB:", job)

        if ad_product == "clip":
            send_flow_clip(from_number)
        elif ad_product == "6_monas":
            send_flow_6_monas(from_number)
        elif is_organic_message(text):
            send_flow_6_monas(from_number)
        else:
            send_flow_6_monas(from_number)

    except Exception as e:
        print("ERROR EN FLUJO:", str(e))
    finally:
        processing_users.discard(from_number)

def worker():
    while True:
        job = job_queue.get()
        try:
            process_job(job)
        finally:
            job_queue.task_done()

worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

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
    print("WEBHOOK:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Ignorar status callbacks
        if "statuses" in value:
            return "ok", 200

        if "messages" not in value:
            return "ok", 200

        message = value["messages"][0]
        from_number = message["from"]
        message_id = message.get("id")
        text = get_message_text(message)
        ad_product = detect_ad_product(message, value)

        print("NUMERO:", from_number)
        print("TEXTO:", text)
        print("PRODUCTO DETECTADO:", ad_product)

        # Deduplicar por message_id
        if message_id and message_id in processed_message_ids:
            print("MENSAJE REPETIDO IGNORADO:", message_id)
            return "ok", 200

        if message_id:
            processed_message_ids.add(message_id)

        # Si ya recibió flujo, no volver a responder
        if from_number in responded_users:
            print(f"{from_number} ya recibió respuesta inicial. No responder.")
            return "ok", 200

        # Si ya está procesándose, no reenfile
        if from_number in processing_users:
            print(f"{from_number} ya está en procesamiento. Ignorar retry.")
            return "ok", 200

        # Marcar ANTES de responder a Meta
        responded_users.add(from_number)
        processing_users.add(from_number)

        # Encolar trabajo y responder inmediato
        job_queue.put({
            "from_number": from_number,
            "text": text,
            "ad_product": ad_product
        })

    except Exception as e:
        print("ERROR WEBHOOK:", str(e))

    return "ok", 200

if __name__ == "__main__":
    app.run(port=5000)
