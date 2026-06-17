import os
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_PATH = os.path.join(BASE_DIR, "data", "chroma")
MODEL_NAME  = "clip-ViT-B-32"

_model      = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client      = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection("products")
    return _collection


def _deduplicate(metadatas: list, n: int) -> list:
    seen   = set()
    result = []
    for meta in metadatas:
        pid = meta["product_id"]
        if pid not in seen:
            seen.add(pid)
            result.append(meta)
        if len(result) == n:
            break
    return result


def search_by_text(query: str, n: int = 3) -> list:
    vec    = _get_model().encode(query).tolist()
    result = _get_collection().query(query_embeddings=[vec], n_results=n * 2)
    return _deduplicate(result["metadatas"][0], n)


def search_by_image(image_path: str, n: int = 3) -> list:
    img    = np.array(Image.open(image_path).convert("RGB"))
    vec    = _get_model().encode(img).tolist()
    result = _get_collection().query(query_embeddings=[vec], n_results=n * 2)
    return _deduplicate(result["metadatas"][0], n)