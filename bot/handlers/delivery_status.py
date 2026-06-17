import sqlite3
import re
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GCP_API_KEY"))

DB_PATH = "data/bot.db"

OUT_OF_SCOPE_REPLY = (
    "I can only assist with questions about Nappa Milano products. "
    "Please use the menu to select a topic."
)

# Keywords that signal a delivery / order tracking question.
_DELIVERY_KEYWORDS = re.compile(
    r"pesanan|order|orderan|paket|package"
    r"|pengiriman|delivery|deliveri|kirim|kiriman"
    r"|resi|tracking|lacak|track"
    r"|status|sampai|tiba|arrived|kurir|courier"
    r"|nama|name|nomor|nomer|hp|phone|telepon|telp|handphone"
    r"|belum|sudah|kapan|when|where|mana|dimana",
    re.IGNORECASE,
)


def _is_out_of_scope(text: str) -> bool:
    """Return True when the message has no delivery/order-related keywords."""
    return not bool(_DELIVERY_KEYWORDS.search(text))

SCHEMA = """
TABLE orders:
  order_id       TEXT  -- internal ID, never expose or use in WHERE
  customer_name  TEXT  -- full name of the customer
  customer_phone TEXT  -- customer phone number, e.g. 08123456789
  total_price    REAL
  status         TEXT  -- pending | processing | shipped | delivered | cancelled
  ordered_at     DATETIME

TABLE order_items:
  item_id      TEXT
  order_id     TEXT
  product_name TEXT
  size         TEXT
  quantity     INTEGER
  unit_price   REAL

TABLE shipments:
  shipment_id       TEXT
  order_id          TEXT
  courier           TEXT
  tracking_number   TEXT
  current_status    TEXT  -- picked_up | in_transit | out_for_delivery | delivered
  origin_city       TEXT
  dest_city         TEXT
  shipped_at        DATETIME
  estimated_arrival DATETIME
  delivered_at      DATETIME
"""

sql_model = genai.GenerativeModel(
    model_name="gemini-3.5-flash",
    system_instruction=f"""You are a SQL generator. Given a user question about their order, generate a single valid SQLite query.

Database schema:
{SCHEMA}

Rules:
- Output ONLY the raw SQL query, no explanation, no markdown, no backticks.
- Users identify themselves by name or phone number, never by order_id.
- Always search using LOWER(customer_name) LIKE LOWER('%name%') or customer_phone = 'number'.
- Never use order_id in the WHERE clause.
- Always JOIN order_items and shipments when relevant.
- Never use DROP, DELETE, UPDATE, INSERT, or any destructive statement.
- If the question cannot be answered with the schema, output: UNSUPPORTED"""
)

answer_model = genai.GenerativeModel(
    model_name="gemini-3.5-flash",
    system_instruction="""You are a helpful customer service assistant for Nappa Milano, an Indonesian leather shoe brand.
Given a user question and query results from the database, answer naturally and helpfully.
Respond in the same language the user uses (Indonesian or English).
Be concise and friendly. If the result is empty, tell the user the order was not found and suggest they double-check their name or phone number.

If the database results are unrelated to order tracking, or the user is asking something outside of order/delivery status, respond only with:
"I can only assist with order tracking. Please use the menu to select a topic."

If the user's message is not a question about order or delivery status, output: UNSUPPORTED"""
)


def _generate_sql(user_message: str) -> str:
    response = sql_model.generate_content(user_message)
    return response.text.strip()


def _execute_sql(query: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _format_results(rows: list[dict]) -> str:
    if not rows:
        return "No results found."
    lines = []
    for row in rows:
        lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
    return "\n".join(lines)


def handle_delivery(user_message: str) -> dict:
    # Fast out-of-scope guard — skip SQL model entirely for irrelevant input.
    if _is_out_of_scope(user_message):
        return {
            "text": OUT_OF_SCOPE_REPLY,
            "sql":  None,
            "rows": []
        }

    sql = _generate_sql(user_message)

    if sql == "UNSUPPORTED":
        return {
            "text": "Sorry, I can only help you track your order status. Could you provide the customer's name or phone number used during the order?",
            "sql":  None,
            "rows": []
        }

    forbidden = ["drop", "delete", "update", "insert", "alter", "truncate"]
    if any(word in sql.lower() for word in forbidden):
        return {
            "text": "Sorry, an error occurred. Please try again.",
            "sql":  sql,
            "rows": []
        }

    try:
        rows = _execute_sql(sql)
    except Exception as e:
        return {
            "text": "Sorry, I couldn't find your order details. Please make sure the name or phone number is correct.",
            "sql":  sql,
            "rows": [],
            "error": str(e)
        }

    result_text = _format_results(rows)

    prompt = f"""User question: {user_message}

Database results:
{result_text}

Answer the user's question based on the results above."""

    response = answer_model.generate_content(prompt)

    return {
        "text": response.text,
        "sql":  sql,
        "rows": rows
    }