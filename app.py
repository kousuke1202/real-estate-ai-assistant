from flask import Flask, render_template, request, redirect, url_for
import os
import sqlite3
import smtplib
from pathlib import Path
from email.mime.text import MIMEText

import requests
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()

app = Flask(__name__)
DB_PATH = Path("data/real_estate.db")

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
LINE_CONFIGURATION = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN) if LINE_CHANNEL_ACCESS_TOKEN else None
handler = WebhookHandler(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            rent TEXT NOT NULL,
            layout TEXT NOT NULL,
            status TEXT NOT NULL,
            available_date TEXT,
            requirements TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            property_id INTEGER,
            customer_type TEXT,
            message TEXT NOT NULL,
            auto_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            name TEXT NOT NULL,
            phone TEXT,
            preferred_date TEXT,
            note TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    seed_demo_properties()


def seed_demo_properties():
    conn = get_db_connection()
    existing = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    if existing == 0:
        conn.execute(
            """
            INSERT INTO properties (name, address, rent, layout, status, available_date, requirements, description)
            VALUES
                ('レジデンス新宿101', '東京都新宿区西新宿1-1-1', '¥180,000 / 月', '2LDK', 'available', '2026-10-05', '収入条件あり、ペ���ト不可、入居時期相談', '駅徒歩5分の2LDK。南向きで明るく、設備充実。'),
                ('グリーンハイツ渋谷', '東京都渋谷区道玄坂2-4-8', '¥220,000 / 月', '3LDK', 'available', '2026-10-20', '事務所利用不可、入居時期相談', '都心に位置する3LDK。広いリビングと洗練された内装。'),
                ('サンライズ大森', '東京都大田区大森西2-3-6', '¥150,000 / 月', '1LDK', 'reserved', '2026-11-01', '単身者歓迎、事務所利用不可', '落ち着いた雰囲気の1LDK。大森駅まで徒歩8分。')
            """
        )
        conn.commit()
    conn.close()


def get_properties():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM properties ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_property_by_id(property_id):
    if not property_id:
        return None
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    conn.close()
    return row


def get_inquiries():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT i.*, p.name AS property_name FROM inquiries i LEFT JOIN properties p ON p.id = i.property_id ORDER BY i.created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_reservations():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT r.*, p.name AS property_name FROM reservations r LEFT JOIN properties p ON p.id = r.property_id ORDER BY r.created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def find_property_for_message(message):
    text = (message or "").strip()
    if not text:
        return None

    query = text.lower()
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT * FROM properties
        WHERE LOWER(name) LIKE ? OR LOWER(address) LIKE ? OR LOWER(description) LIKE ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (f"%{query}%", f"%{query}%", f"%{query}%"),
    ).fetchone()
    conn.close()
    return row


def call_openai_for_response(message, property_record=None):
    if not OPENAI_API_KEY:
        return None

    property_context = ""
    if property_record:
        property_context = (
            f"物件名: {property_record['name']}\n"
            f"住所: {property_record['address']}\n"
            f"賃料: {property_record['rent']}\n"
            f"間取り: {property_record['layout']}\n"
            f"状態: {property_record['status']}\n"
            f"入居可能日: {property_record['available_date']}\n"
            f"条件: {property_record['requirements']}\n"
            f"説明: {property_record['description']}"
        )

    prompt = (
        "あなたは不動産会社の問い合わせ対応アシスタントです。"
        "丁寧で親しみやすい日本語で返信してください。"
        "要点を簡潔にまとめ、内見や資料請求の案内を含めてください。\n\n"
        f"物件情報:\n{property_context}\n\n"
        f"ユーザーの問い合わせ:\n{message}"
    )

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return content.strip()
    except Exception:
        return None


def send_admin_notification(subject, message):
    if SLACK_WEBHOOK_URL:
        try:
            requests.post(SLACK_WEBHOOK_URL, json={"text": f"[{subject}]\n{message}"}, timeout=10)
        except Exception:
            pass

    if not ADMIN_EMAIL or not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        return

    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ADMIN_EMAIL

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        pass


def generate_auto_response(message, property_record=None):
    property_record = property_record or find_property_for_message(message)
    text = (message or "").lower()

    ai_response = call_openai_for_response(message, property_record)
    if ai_response:
        return ai_response

    if not property_record:
        if any(keyword in text for keyword in ["空室", "空いて", "空き", "まだ空", "空いてる"]):
            return "現在の在庫を確認できませんでした。物件名またはエリアをご指定いただければ、空室状況をご案内いたします。"
        return (
            "お問い合わせありがとうございます。物件名や希望条件をご入力ください。"
            "例：新宿の2LDK、渋谷の空室、内見希望など。"
        )

    if any(keyword in text for keyword in ["空室", "空いて", "空き", "まだ空", "空いてる"]):
        if property_record["status"] == "available":
            return (
                f"ご連絡ありがとうございます。{property_record['name']} は現在空室がございます。"
                f"賃料は {property_record['rent']}、間取りは {property_record['layout']}です。"
                f"入居可能時期は {property_record['available_date']} です。"
                "内見をご希望でしたら、担当者よりご案内いたします。"
            )
        return (
            f"ご連絡ありがとうございます。{property_record['name']} は��在満室のため、"
            "空室のご案内はできかねます。別の物件や今後の空室予定もご確認できますので、"
            "ご希望条件をお知らせください。"
        )

    if any(keyword in text for keyword in ["家賃", "賃料", "月額"]):
        return (
            f"{property_record['name']} の賃料は {property_record['rent']} です。"
            f"詳細や初期費用についてもご案内可能です。"
        )

    if any(keyword in text for keyword in ["間取り", "layout"]):
        return (
            f"{property_record['name']} の間取りは {property_record['layout']} です。"
            "ご希望の広さや人数に合うかもしれません。"
        )

    if any(keyword in text for keyword in ["内見", "見学", "見に行きたい", "予約"]):
        return (
            f"内見はご予約可能です。{property_record['available_date']} 以降のご希望日をお知らせください。"
            "担当者が調整いたします。"
        )

    if any(keyword in text for keyword in ["条件", "入居条件", "利用条件", "ペット"]):
        return (
            f"入居条件は {property_record['requirements']} です。"
            "ご不明点があれば、個別にご案内いたします。"
        )

    return (
        f"ご連絡ありがとうございます。{property_record['name']} は {property_record['address']} に所在し、"
        f"間取りは {property_record['layout']}、賃料は {property_record['rent']}です。"
        "必要でしたら、内見予約や詳細資料のご案内も対応可能です。"
    )


@app.route("/")
def index():
    return render_template("index.html", properties=get_properties())


@app.route("/inquiry", methods=["POST"])
def inquiry():
    form_data = request.form
    property_record = get_property_by_id(form_data.get("property_id"))
    auto_response = generate_auto_response(form_data.get("message", ""), property_record)

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO inquiries (name, email, phone, property_id, customer_type, message, auto_response)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            form_data.get("name", "").strip(),
            form_data.get("email", "").strip(),
            form_data.get("phone", "").strip(),
            form_data.get("property_id"),
            form_data.get("customer_type", "一般"),
            form_data.get("message", "").strip(),
            auto_response,
        ),
    )
    conn.commit()
    conn.close()

    property_name = property_record["name"] if property_record else "未選択"
    send_admin_notification(
        "新規お問い合わせ",
        f"名前: {form_data.get('name', '').strip()}\n"
        f"メール: {form_data.get('email', '').strip() or '未記入'}\n"
        f"電話番号: {form_data.get('phone', '').strip() or '未記入'}\n"
        f"物件: {property_name}\n"
        f"内容: {form_data.get('message', '').strip()}\n"
        f"自動返信: {auto_response}",
    )

    return render_template(
        "thanks.html",
        property=property_record,
        response=auto_response,
        inquiry=form_data,
    )


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        properties=get_properties(),
        inquiries=get_inquiries(),
        reservations=get_reservations(),
    )


@app.route("/properties/new")
def new_property():
    return render_template("property_form.html")


@app.route("/properties", methods=["POST"])
def create_property():
    form_data = request.form
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO properties (name, address, rent, layout, status, available_date, requirements, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            form_data.get("name", "").strip(),
            form_data.get("address", "").strip(),
            form_data.get("rent", "").strip(),
            form_data.get("layout", "").strip(),
            form_data.get("status", "available"),
            form_data.get("available_date", "").strip(),
            form_data.get("requirements", "").strip(),
            form_data.get("description", "").strip(),
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/reservations/new")
def new_reservation():
    return render_template("reservation_form.html", properties=get_properties())


@app.route("/reservations", methods=["POST"]) 
def create_reservation():
    form = request.form
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO reservations (property_id, name, phone, preferred_date, note, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            form.get("property_id"),
            form.get("name", "").strip(),
            form.get("phone", "").strip(),
            form.get("preferred_date", "").strip(),
            form.get("note", "").strip(),
            "pending",
        ),
    )
    conn.commit()
    conn.close()

    property_name = get_property_by_id(form.get("property_id"))
    property_name = property_name["name"] if property_name else "未選択"
    send_admin_notification(
        "新規内見予約",
        f"名前: {form.get('name','').strip()}\n"
        f"電話番号: {form.get('phone','').strip()}\n"
        f"物件: {property_name}\n"
        f"希望日: {form.get('preferred_date','').strip()}\n"
        f"備考: {form.get('note','').strip() or 'なし'}",
    )
    return redirect(url_for("admin"))


@app.route("/reservations/<int:reservation_id>/status", methods=["POST"]) 
def update_reservation_status(reservation_id):
    status = request.form.get("status", "pending")
    conn = get_db_connection()
    conn.execute("UPDATE reservations SET status = ? WHERE id = ?", (status, reservation_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.route("/line/webhook", methods=["POST"])
def line_webhook():
    if not LINE_CHANNEL_SECRET or not LINE_CONFIGURATION:
        return "LINE is not configured", 500

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK", 200


if handler is not None:
    @handler.add(MessageEvent)
    def handle_message(event):
        if not isinstance(event.message, TextMessageContent):
            return

        text = event.message.text
        property_record = find_property_for_message(text)
        response = generate_auto_response(text, property_record)

        with ApiClient(LINE_CONFIGURATION) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=response)],
                )
            )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
