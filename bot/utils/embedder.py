# bot/utils/embedder.py
import chromadb
from sentence_transformers import SentenceTransformer
from PIL import Image
import pandas as pd
import ast

model = SentenceTransformer("clip-ViT-B-32")
client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_or_create_collection("products")


# ── INDEXING (jalankan sekali saat setup) ──────────────────────────

def index_products(csv_path="data/products.csv"):
    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        pid = str(row["product_id"])

        # 1. Text entry
        text = f"{row['product_name']} {row['shoe_model']} {row['material']} {row['category']} {row['description']}"
        text_vec = model.encode(text).tolist()

        metadata = {
            "product_id":      pid,
            "product_name":    str(row["product_name"]),
            "price":           float(row["price"]) if pd.notna(row["price"]) else 0,
            "sizes_available": str(row["sizes_available"]),
            "stock_total":     int(row["stock_total"]) if pd.notna(row["stock_total"]) else 0,
            "stock_per_size":  str(row["stock_per_size"]),
            "rating":          float(row["rating"]) if pd.notna(row["rating"]) else 0,
            "category":        str(row["category"]),
            "image_local_path": str(row["image_local_paths"]),
            "type": "text"
        }

        collection.upsert(
            ids=[f"{pid}_text"],
            embeddings=[text_vec],
            documents=[text],
            metadatas=[metadata]
        )

        # 2. Image entry
        img_path = str(row["image_local_paths"])
        try:
            img_vec = model.encode(Image.open(img_path)).tolist()
            img_metadata = {**metadata, "type": "image"}
            collection.upsert(
                ids=[f"{pid}_image"],
                embeddings=[img_vec],
                metadatas=[img_metadata]
            )
        except Exception as e:
            print(f"Skip image {img_path}: {e}")

    print(f"Indexed {len(df)} products.")


# ── QUERYING (dipanggil saat bot dapat pesan) ──────────────────────

def search_by_text(query: str, n=3):
    vec = model.encode(query).tolist()
    return _query(vec, n)

def search_by_image(image_path: str, n=3):
    vec = model.encode(Image.open(image_path)).tolist()
    return _query(vec, n)

def _query(vec, n):
    results = collection.query(query_embeddings=[vec], n_results=n * 2)
    # deduplikasi berdasarkan product_id
    seen = set()
    unique = []
    for meta in results["metadatas"][0]:
        pid = meta["product_id"]
        if pid not in seen:
            seen.add(pid)
            unique.append(meta)
        if len(unique) == n:
            break
    return unique