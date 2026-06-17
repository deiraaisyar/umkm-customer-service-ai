"""
seed_dummy.py — Populate bot.db with dummy conversations, messages, and ratings.
Run once from the project root: python dashboard/seed_dummy.py
"""

import sqlite3
import uuid
import random
from datetime import datetime, timedelta

DB_PATH = "data/bot.db"

USERS = [f"user_{100 + i}" for i in range(30)]

FEEDBACK_POOL = [
    # Positive
    ("Really helpful! Found the shoe I was looking for quickly.", "Positive"),
    ("Great service, very fast and accurate answers.", "Positive"),
    ("Love the product info feature, I could find size info easily.", "Positive"),
    ("The payment guide was very clear, thank you!", "Positive"),
    ("Super responsive bot, highly recommend!", "Positive"),
    ("I got all the info I needed without any problems.", "Positive"),
    ("Easy to use and very informative.", "Positive"),
    ("Quick response and accurate product details.", "Positive"),
    ("Amazing experience, will use again!", "Positive"),
    ("Helped me track my order in seconds.", "Positive"),
    # Neutral
    ("It was okay, answered my question but nothing special.", "Neutral"),
    ("Average, the info was helpful but could be more detailed.", "Neutral"),
    ("Decent service overall.", "Neutral"),
    ("It worked, though I had to rephrase my question a couple times.", "Neutral"),
    ("Good enough for basic questions.", "Neutral"),
    ("Got the info I needed, not bad.", "Neutral"),
    ("It was fine.", "Neutral"),
    # Negative
    ("Couldn't find the product I was looking for.", "Negative"),
    ("The bot didn't understand my question.", "Negative"),
    ("Not helpful at all, had to contact CS manually.", "Negative"),
    ("Took too long and gave me the wrong info.", "Negative"),
    ("Very frustrating experience.", "Negative"),
    ("The answers were not relevant to what I asked.", "Negative"),
    # No feedback (None)
    (None, None),
    (None, None),
    (None, None),
    (None, None),
    (None, None),
]

SCORE_SENTIMENT_MAP = {
    1: "Negative",
    2: "Negative",
    3: "Neutral",
    4: "Positive",
    5: "Positive",
}

USER_MESSAGES = [
    ("Apakah sepatu loafer tersedia?", "product_info"),
    ("Berapa harga sepatu kulit pria?", "product_info"),
    ("Ada ukuran 43 tidak?", "product_info"),
    ("Mau lihat sepatu wanita material suede.", "product_info"),
    ("Cara bayar pakai QRIS gimana?", "payment"),
    ("Transfer ke rekening mana?", "payment"),
    ("Apakah ada COD?", "payment"),
    ("Status pesanan saya sudah sampai mana?", "delivery"),
    ("Pesanan atas nama Budi Santoso sudah kirim belum?", "delivery"),
    ("Cek resi nomor 08123456789.", "delivery"),
    ("Kapan pesanan saya tiba?", "delivery"),
    ("Stok sepatu chelsea boot masih ada?", "product_info"),
    ("Rekomendasi sepatu kasual pria?", "product_info"),
]

BOT_RESPONSES = [
    ("Here are some matching products for you...", "product_info"),
    ("The price range for leather shoes is Rp 629,000 – Rp 959,000.", "product_info"),
    ("Size 43 is available for these models...", "product_info"),
    ("Sorry, I couldn't find matching products. Could you describe more?", "product_info"),
    ("You can pay via QRIS by scanning the code available on Shopee.", "payment"),
    ("Please transfer to BCA: 1234567890.", "payment"),
    ("COD is not supported. Please use bank transfer or QRIS.", "payment"),
    ("Your order is currently in transit.", "delivery"),
    ("Order for Budi Santoso has been shipped via JNE.", "delivery"),
    ("I couldn't find an order linked to that phone number.", "delivery"),
    ("Your estimated delivery is within 2-3 business days.", "delivery"),
]


def run():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    now = datetime.now()

    inserted = 0
    for user_id in USERS:
        n_sessions = random.randint(1, 3)
        for _ in range(n_sessions):
            conv_id    = str(uuid.uuid4())
            started_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            ended_at   = started_at + timedelta(minutes=random.randint(3, 25))

            cur.execute(
                "INSERT OR IGNORE INTO conversations (conv_id, user_id, started_at, ended_at, message_count) VALUES (?,?,?,?,?)",
                (conv_id, user_id, started_at.isoformat(), ended_at.isoformat(), 0)
            )

            msg_count = 0
            n_exchanges = random.randint(1, 4)
            for i in range(n_exchanges):
                t_offset = timedelta(minutes=i * 2)

                # User message
                user_msg, intent = random.choice(USER_MESSAGES)
                msg_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT OR IGNORE INTO messages (msg_id, conv_id, role, content, intent_label, sent_at) VALUES (?,?,?,?,?,?)",
                    (msg_id, conv_id, "user", user_msg, intent, (started_at + t_offset).isoformat())
                )
                msg_count += 1

                # Bot response
                bot_msg, _ = random.choice(BOT_RESPONSES)
                msg_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT OR IGNORE INTO messages (msg_id, conv_id, role, content, intent_label, sent_at) VALUES (?,?,?,?,?,?)",
                    (msg_id, conv_id, "assistant", bot_msg, intent, (started_at + t_offset + timedelta(seconds=5)).isoformat())
                )
                msg_count += 1

            cur.execute(
                "UPDATE conversations SET message_count = ? WHERE conv_id = ?",
                (msg_count, conv_id)
            )

            # Rating: ~80% of sessions get a rating
            if random.random() < 0.80:
                score = random.choices([1, 2, 3, 4, 5], weights=[5, 8, 15, 35, 37])[0]
                feedback_tuple = random.choice(FEEDBACK_POOL)
                feedback_text, feedback_sentiment = feedback_tuple

                # If no text feedback, derive sentiment from score
                sentiment = feedback_sentiment if feedback_text else SCORE_SENTIMENT_MAP[score]

                rating_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT OR IGNORE INTO ratings (rating_id, conv_id, score, feedback_text, sentiment, rated_at) VALUES (?,?,?,?,?,?)",
                    (rating_id, conv_id, score, feedback_text, sentiment, ended_at.isoformat())
                )
                inserted += 1

    conn.commit()
    conn.close()
    print(f"Done. Inserted dummy data for {len(USERS)} users. {inserted} ratings recorded.")


if __name__ == "__main__":
    run()
