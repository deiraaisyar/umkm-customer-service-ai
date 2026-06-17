import os
import sqlite3
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "bot.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_migrations():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN latency REAL")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

# Run migrations automatically
try:
    run_migrations()
except Exception:
    pass

def create_conversation(user_id: str) -> str:
    """Create a new conversation session and return conv_id."""
    conv_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO conversations (conv_id, user_id, started_at) VALUES (?, ?, ?)",
            (conv_id, user_id, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()
    return conv_id

def log_message(conv_id: str, role: str, content: str, intent_label: str = None, latency: float = None):
    """Log a user or assistant message to the database and increment message count."""
    msg_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO messages (msg_id, conv_id, role, content, intent_label, sent_at, latency) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conv_id, role, content, intent_label, datetime.now().isoformat(), latency)
        )
        conn.execute(
            "UPDATE conversations SET message_count = message_count + 1 WHERE conv_id = ?",
            (conv_id,)
        )
        conn.commit()
    finally:
        conn.close()

def save_rating(conv_id: str, score: int, feedback_text: str = None, sentiment: str = None):
    """Save a user rating to the database."""
    rating_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO ratings (rating_id, conv_id, score, feedback_text, sentiment, rated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (rating_id, conv_id, score, feedback_text, sentiment, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def end_conversation(conv_id: str):
    """Mark a conversation as ended."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE conversations SET ended_at = ? WHERE conv_id = ?",
            (datetime.now().isoformat(), conv_id)
        )
        conn.commit()
    finally:
        conn.close()
