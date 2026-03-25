from flask import Flask, request
import requests
import os
import time
import sqlite3
from contextlib import closing

app = Flask(__name__)

VERIFY_TOKEN = "encanto_token_123"
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

GRAPH_URL = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
DB_PATH = os.getenv("DB_PATH", "bot_state.db")

# 7 días
REPLY_COOLDOWN_SECONDS = 7 * 24 * 60 * 60

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

# Imágenes subidas a Meta
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

# =========================================================
# BIBLIOTECA DE ANUNCIOS -> PRODUCTO / ORIGEN
# Aquí metes IDs reales de anuncios, campañas o textos clave
# =========================================================
AD_SOURCE_MAP = {
    # EJEMPLOS:
    # "123456789012345": {"origin": "ad_clip_main", "product": "clip"},
    # "987654321098765": {"origin": "ad_6_monas_main", "product": "6_monas"},
}

# Fallback por palabras si todavía no has llenado los IDs
CLIP_KEYWORDS = [
    "clip", "cortina", "cortinas", "5 clips",
    "instala facil", "instala fácil", "semi natural clip"
]

MONAS_KEYWORDS = [
    "6_monas", "6 monas", "6 moñas", "moñas",
    "extension 6 moñas", "extensiones premium",
    "loose wave", "crespas", "lisas"
]


# =========================
# DB
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(get_conn()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                processed_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_state (
                wa_id TEXT PRIMARY KEY,
                last_reply_at INTEGER,
                last_origin TEXT,
                last_product TEXT
            )
        """)
        conn.commit()

def is_processed_message(message_id):
    if not message_id:
        return False
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ? LIMIT 1",
            (message_id,)
        ).fetchone()
        return row is not None

def mark_processed_message(message_id):
    if not message_id:
        return
    with closing(get_conn()) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
            (message_id, int(time.time()))
        )
        conn.commit()

def get_user_state(wa_id):
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT wa_id, last_reply_at, last_origin, last_product FROM user_state WHERE wa_id = ? LIMIT 1",
            (wa_id,)
        ).fetchone()
        return dict(row) if row else None

def upsert_user_state(wa_id, last_reply_at, last_origin, last_product):
    with closing(get_conn()) as conn:
        conn.execute("""
            INSERT INTO user_state (wa_id, last_reply_at, last_origin, last_product)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(wa_id) DO UPDATE SET
                last_reply_at = excluded.last_reply_at,
                last_origin = excluded.last_origin,
                last_product = excluded.last_product
        """, (wa_id, last_reply_at, last_origin, last_product))
        conn.commit()


# =========================
# WhatsApp send helpers
# =========================
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

    response = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("TEXT STATUS:", response.status_code)
    print("TEXT RESPONSE:", response.text)
    return response

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

    response = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=30)
    print("IMAGE STATUS:", response.status_code)
    print("IMAGE RESPONSE:", response.text)
    return response


# =========================
# Logic helpers
# =========================
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

def extract_strings(obj):
    found = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                found.append(k.lower())

            if isinstance(v, str):
                found.append(v.lower())
            elif isinstance(v, dict):
                found.extend(extract_strings(v))
            elif isinstance(v, list):
                for item in v:
                    found.extend(extract_strings(item))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(extract_strings(item))

    return found

def detect_ad_mapping(message, value):
    """
    Busca IDs o textos del webhook que coincidan con la biblioteca AD_SOURCE_MAP.
    """
    candidates = extract_strings(message) + extract_strings(value)
    joined = " | ".join(candidates)

    for known_id_or_key, mapping in AD_SOURCE_MAP.items():
        if known_id_or_key.lower() in joined:
            return mapping

    return None

def detect_ad_product_by_keywords(message, value):
    candidates = extract_strings(message) + extract_strings(value)
    joined = " | ".join(candidates)

    for key in CLIP_KEYWORDS:
        if key in joined:
            return "clip"

    for key in MONAS_KEYWORDS:
        if key in joined:
            return "6_monas"

    return None

def get_origin_and_product(message, value, text):
    """
    Devuelve origin + product.
    origin puede ser:
    - organic
    - ad_clip_main
    - ad_6_monas_main
    - ad_clip_unknown
    - ad_6_monas_unknown
    """
    mapped = detect_ad_mapping(message, value)
    if mapped:
        return mapped["origin"], mapped["product"]

    keyword_product = detect_ad_product_by_keywords(message, value)
    if keyword_product == "clip":
        return "ad_clip_unknown", "clip"
    if keyword_product == "6_monas":
        return "ad_6_monas_unknown", "6_monas"

    # Si no vino claro de anuncio, se va como orgánico
    return "organic", "6_monas"

def should_auto_reply(wa_id, current_origin):
    user = get_user_state(wa_id)

    if not user:
        print("DECISION: responder porque es usuario nuevo")
        return True

    now_ts = int(time.time())
    last_reply_at = int(user.get("last_reply_at") or 0)
    last_origin = user.get("last_origin") or ""
    elapsed = now_ts - last_reply_at

    # Si cambia el origen, sí responde
    if current_origin != last_origin:
        print(f"DECISION: responder porque cambió origen ({last_origin} -> {current_origin})")
        return True

    # Si pasó el cooldown, sí responde
    if elapsed >= REPLY_COOLDOWN_SECONDS:
        print(f"DECISION: responder porque pasaron {elapsed} segundos")
        return True

    # Si es mismo origen y poco tiempo, no responde
    print(f"DECISION: NO responder. Mismo origen ({current_origin}) y solo han pasado {elapsed} segundos")
    return False

def mark_reply_sent(wa_id, origin, product):
    upsert_user_state(
        wa_id=wa_id,
        last_reply_at=int(time.time()),
        last_origin=origin,
        last_product=product
    )

def send_block(to, images, pause_each=0.35, pause_after=0.8):
    for media_id in images:
        send_image(to, media_id)
        time.sleep(pause_each)
    time.sleep(pause_after)

def send_flow_6_monas(to):
    send_text(to, TEXT_6_MONAS)
    time.sleep(0.8)

    send_text(to, "✨ EXTENSIONES LISAS DISPONIBLES")
    time.sleep(0.5)
    send_block(to, IMAGES_LISAS, pause_each=0.35, pause_after=0.8)

    send_text(to, "🔥 EXTENSIONES CRESPAS (FULL VOLUMEN)")
    time.sleep(0.5)
    send_block(to, IMAGES_CRESPAS, pause_each=0.35, pause_after=0.8)

    send_text(to, "🌊 LOOSE WAVE (ONDULADAS NATURALES)")
    time.sleep(0.5)
    send_block(to, IMAGES_ONDULADAS, pause_each=0.35, pause_after=0.8)

    send_text(to, ASK_CITY)

def send_flow_clip(to):
    send_text(to, TEXT_CLIP)
    time.sleep(0.8)

    send_text(to, "*EXTENSIONES CLIP*")
    time.sleep(0.5)
    send_block(to, IMAGES_CLIP, pause_each=0.35, pause_after=0.8)

    send_text(to, ASK_CITY)


# =========================
# Routes
# =========================
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
    data = request.get_json(silent=True) or {}
    print("WEBHOOK RECIBIDO:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # ignorar status sent/delivered/read
        if "statuses" in value:
            return "ok", 200

        if "messages" not in value:
            return "ok", 200

        message = value["messages"][0]
        from_number = message.get("from")
        message_id = message.get("id")

        if not from_number:
            return "ok", 200

        # evitar reprocesar el mismo mensaje exacto
        if message_id and is_processed_message(message_id):
            print("MENSAJE REPETIDO IGNORADO:", message_id)
            return "ok", 200

        if message_id:
            mark_processed_message(message_id)

        text = get_message_text(message)
        origin, product = get_origin_and_product(message, value, text)
        # PRUEBA TEMPORAL CORTINA
        origin = "ad_clip_test"
        product = "clip"

        print("NUMERO:", from_number)
        print("TEXTO:", text)
        print("ORIGIN:", origin)
        print("PRODUCT:", product)

        # decidir si responder o no
        #if not should_auto_reply(from_number, origin):
            #return "ok", 200

        # enviar flujo
        if product == "clip":
            send_flow_clip(from_number)
            mark_reply_sent(from_number, origin, product)
            return "ok", 200

        # default: 6 moñas
        send_flow_6_monas(from_number)
        mark_reply_sent(from_number, origin, product)
        return "ok", 200

    except Exception as e:
        print("ERROR PROCESANDO WEBHOOK:", str(e))

    return "ok", 200


init_db()

if __name__ == "__main__":
    app.run(port=5000)
