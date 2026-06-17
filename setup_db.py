import os
import sqlite3
import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from PIL import Image

# ── CONFIG ─────────────────────────────────────────────────────────
CSV_PATH    = "data/products.csv"
CHROMA_PATH = "data/chroma"
DB_PATH     = "data/bot.db"
MODEL_NAME  = "clip-ViT-B-32"

random.seed(42)


# ══════════════════════════════════════════════════════════════════
# 1. CHROMADB — index products
# ══════════════════════════════════════════════════════════════════

def index_products():
    print("=== [1/2] Indexing products ke ChromaDB ===")

    model  = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection("products")
    except Exception:
        pass

    collection = client.create_collection(
        name="products",
        metadata={"hnsw:space": "cosine"}
    )

    df = pd.read_csv(CSV_PATH)
    skipped_images = 0

    for i, row in df.iterrows():
        pid = str(row["product_id"])

        parts = [
            str(row.get("product_name", "")),
            str(row.get("shoe_model", "")),
            str(row.get("material", "")),
            str(row.get("category", "")),
            str(row.get("description", "")),
        ]
        text = " ".join(p for p in parts if p and p != "nan")

        metadata = {
            "product_id":       pid,
            "product_name":     str(row.get("product_name", "")),
            "price":            float(row["price"]) if pd.notna(row.get("price")) else 0.0,
            "sizes_available":  str(row.get("sizes_available", "")),
            "stock_total":      int(row["stock_total"]) if pd.notna(row.get("stock_total")) else 0,
            "stock_per_size":   str(row.get("stock_per_size", "")),
            "rating":           float(row["rating"]) if pd.notna(row.get("rating")) else 0.0,
            "category":         str(row.get("category", "")),
            "material":         str(row.get("material", "")),
            "image_local_path": str(row.get("image_local_paths", "")),
            "type":             "text",
        }

        text_vec = model.encode(text).tolist()
        collection.upsert(
            ids=[f"{pid}_text"],
            embeddings=[text_vec],
            documents=[text],
            metadatas=[metadata],
        )

        img_path = str(row.get("image_local_paths", ""))
        if os.path.exists(img_path):
            try:
                img_array = np.array(Image.open(img_path).convert("RGB"))
                img_vec   = model.encode(img_array).tolist()
                collection.upsert(
                    ids=[f"{pid}_image"],
                    embeddings=[img_vec],
                    metadatas=[{**metadata, "type": "image"}],
                )
            except Exception as e:
                print(f"  [skip image] {img_path}: {e}")
                skipped_images += 1
        else:
            skipped_images += 1

        print(f"  Indexed [{i+1}/{len(df)}] {row.get('product_name', pid)}")

    print(f"Done. {len(df)} produk diindex, {skipped_images} gambar dilewati.\n")

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id       TEXT PRIMARY KEY,
    customer_name  TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    total_price    REAL NOT NULL,
    status         TEXT NOT NULL,   -- pending | processing | shipped | delivered | cancelled
    ordered_at     DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id      TEXT PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders(order_id),
    product_name TEXT NOT NULL,
    size         TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    unit_price   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id       TEXT PRIMARY KEY,
    order_id          TEXT NOT NULL REFERENCES orders(order_id),
    courier           TEXT NOT NULL,
    tracking_number   TEXT NOT NULL,
    current_status    TEXT NOT NULL,  -- picked_up | in_transit | out_for_delivery | delivered
    origin_city       TEXT NOT NULL,
    dest_city         TEXT NOT NULL,
    shipped_at        DATETIME,
    estimated_arrival DATETIME,
    delivered_at      DATETIME
);

CREATE TABLE IF NOT EXISTS conversations (
    conv_id       TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    started_at    DATETIME NOT NULL,
    ended_at      DATETIME,
    message_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    msg_id       TEXT PRIMARY KEY,
    conv_id      TEXT NOT NULL REFERENCES conversations(conv_id),
    role         TEXT NOT NULL,  -- user | assistant
    content      TEXT NOT NULL,
    intent_label TEXT,
    sent_at      DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS ratings (
    rating_id     TEXT PRIMARY KEY,
    conv_id       TEXT NOT NULL REFERENCES conversations(conv_id),
    score         INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
    feedback_text TEXT,
    sentiment     TEXT,
    rated_at      DATETIME NOT NULL
);
"""

DUMMY_PRODUCTS = [
    ("Yuri Penny Black",         629000),
    ("Gail Dainty Black",        689000),
    ("Gale Soccer Black",        739000),
    ("Luther Penny Green",       769000),
    ("Moss Derby Zebra",         709000),
    ("Damian Tassel Brown",      869000),
    ("Chelsea Boot Tan",         899000),
    ("Oxford Brogue Black",      959000),
    ("Loafer Slip-on Brown",     829000),
    ("Derby Classic White",      779000),
]

COURIERS  = ["JNE", "J&T", "SiCepat", "Anteraja", "Ninja Xpress"]
CITIES    = ["Jakarta", "Bandung", "Surabaya", "Medan", "Yogyakarta", "Semarang", "Makassar"]
STATUSES  = ["pending", "processing", "shipped", "delivered", "delivered", "delivered"]
SHIP_STAT = ["picked_up", "in_transit", "out_for_delivery", "delivered"]
NAMES     = ["Budi Santoso", "Rina Marlina", "Agus Prasetyo", "Dewi Kurnia",
             "Hendra Wijaya", "Siti Rahayu", "Fajar Nugroho", "Maya Putri",
             "Doni Setiawan", "Laila Fitriani"]


def generate_dummy_orders(conn, n=20):
    cur = conn.cursor()
    now = datetime.now()

    for i in range(1, n + 1):
        order_id   = f"ORD-{i:04d}"
        name       = random.choice(NAMES)
        phone      = f"08{random.randint(100000000, 999999999)}"
        status     = random.choice(STATUSES)
        ordered_at = now - timedelta(days=random.randint(1, 30))


        n_items    = random.randint(1, 3)
        items      = random.sample(DUMMY_PRODUCTS, n_items)
        total      = sum(p * random.randint(1, 2) for _, p in items)

        cur.execute(
            "INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?)",
            (order_id, name, phone, total, status, ordered_at.isoformat())
        )

        for j, (pname, price) in enumerate(items, 1):
            qty = random.randint(1, 2)
            cur.execute(
                "INSERT OR IGNORE INTO order_items VALUES (?,?,?,?,?,?)",
                (f"{order_id}-ITM{j}", order_id, pname,
                 str(random.choice([38, 39, 40, 41, 42, 43])),
                 qty, price)
            )

        if status in ("shipped", "delivered"):
            shipped_at = ordered_at + timedelta(days=1)
            eta        = shipped_at + timedelta(days=random.randint(2, 5))
            delivered  = eta if status == "delivered" else None
            ship_stat  = "delivered" if status == "delivered" else random.choice(SHIP_STAT[:3])
            tracking   = f"TRK{random.randint(100000000, 999999999)}"

            cur.execute(
                "INSERT OR IGNORE INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"SHP-{i:04d}", order_id,
                 random.choice(COURIERS), tracking, ship_stat,
                 "Tangerang", random.choice(CITIES),
                 shipped_at.isoformat(), eta.isoformat(),
                 delivered.isoformat() if delivered else None)
            )

    conn.commit()
    print(f"  Inserted {n} dummy orders.\n")


def setup_sqlite():
    print("=== [2/2] Setup SQLite ===")
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    print("  Tabel berhasil dibuat.")
    generate_dummy_orders(conn)
    conn.close()
    print(f"  Database disimpan di {DB_PATH}\n")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    index_products()
    setup_sqlite()
    print("=== Setup selesai. Siap jalankan bot. ===")