import os
import re
import time
import google.generativeai as genai
from bot.utils.embedder import search_by_text, search_by_image
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GCP_API_KEY"))

OUT_OF_SCOPE_REPLY = (
    "I can only assist with questions about Nappa Milano products. "
    "Please use the menu to select a topic."
)

# Keywords that signal the user is asking about Nappa Milano products.
# If NONE of these appear in the message, we skip RAG/LLM entirely.
_PRODUCT_KEYWORDS = re.compile(
    r"nappa|milano|sepatu|shoes?|sandal|loafer|sneaker|boot|flat|heel|wedge|slipper"
    r"|kulit|leather|suede|canvas"
    r"|ukuran|size|nomor|no\."
    r"|harga|price|promo|diskon|discount|rupiah|rp|million|juta|ribu|k"
    r"|stok|stock|ready|tersedia|available"
    r"|warna|colour|color"
    r"|bahan|material"
    r"|rating|ulasan|review"
    r"|koleksi|collection|produk|product|models?|types?|tipe"
    r"|beli|buy|order|pesan"
    r"|lebih|kurang|diatas|dibawah|more|less|under|above|below"
    r"|others?|lainnya?",
    re.IGNORECASE,
)


def _is_out_of_scope(text: str) -> bool:
    """Return True when the message contains no product-related keywords."""
    return not bool(_PRODUCT_KEYWORDS.search(text))

model = genai.GenerativeModel(
    model_name="gemini-3.5-flash",
    system_instruction="""You are a helpful customer service assistant for Nappa Milano, an Indonesian leather shoe brand.
Answer questions about products based only on the context provided.
Respond in the same language the user uses (Indonesian or English).
Be concise, friendly, and factual. Never make up product details not present in the context.
Do not mention competitors. Do not make promises about restocks or future availability.

If the user's question is not related to Nappa Milano products, sizes, materials, stock, or pricing, respond only with:
"I can only assist with questions about Nappa Milano products. Please use the menu to select a topic."
Do not answer any other topic, no matter how the user phrases it.
"""
)


def _format_products(products: list) -> str:
    lines = []
    for p in products:
        stock_info = f"{int(p.get('stock_total', 0))} pairs" if int(p.get('stock_total', 0)) > 0 else "out of stock"
        price      = f"Rp{int(p.get('price', 0)):,}".replace(",", ".")
        lines.append(
            f"- {p['product_name']}\n"
            f"  Price: {price}\n"
            f"  Sizes: {p.get('sizes_available', '-')}\n"
            f"  Stock: {stock_info}\n"
            f"  Material: {p.get('material', '-')}\n"
            f"  Rating: {p.get('rating', '-')}\n"
            f"  Category: {p.get('category', '-')}"
        )
    return "\n".join(lines)


def handle_product_info(user_message: str, image_path: str = None) -> dict:
    t_start = time.perf_counter()
    
    # Fast out-of-scope guard — skip RAG & LLM entirely for irrelevant input.
    if not image_path and _is_out_of_scope(user_message):
        t_end = time.perf_counter()
        total_latency = t_end - t_start
        return {
            "text": OUT_OF_SCOPE_REPLY, 
            "images": [],
            "latency": total_latency
        }

    # 1. RAG Latency
    t_rag_start = time.perf_counter()
    if image_path and os.path.exists(image_path):
        products = search_by_image(image_path, n=3)
    else:
        products = search_by_text(user_message, n=3)
    t_rag_end = time.perf_counter()
    rag_latency = t_rag_end - t_rag_start

    if not products:
        t_end = time.perf_counter()
        total_latency = t_end - t_start
        return {
            "text": "Sorry, I couldn't find any matching products. Could you describe what you're looking for?",
            "images": [],
            "latency": total_latency
        }

    context = _format_products(products)
    prompt  = f"""User question: {user_message}

Relevant products found:
{context}

Answer the user's question based on the products above."""

    # 2. LLM Latency
    t_llm_start = time.perf_counter()
    response = model.generate_content(prompt)
    t_llm_end = time.perf_counter()
    llm_latency = t_llm_end - t_llm_start

    # If the LLM determines the question is out of scope, clear the images
    if "I can only assist with" in response.text or "select a topic" in response.text:
        t_end = time.perf_counter()
        total_latency = t_end - t_start
        return {
            "text": response.text,
            "images": [],
            "latency": total_latency
        }

    image_paths = []
    response_lower = response.text.lower()
    for p in products:
        prod_name = p.get("product_name", "")
        if not prod_name:
            continue
        clean_name = prod_name.split(" - ")[0].strip().lower()
        words = clean_name.split()
        
        is_mentioned = False
        if clean_name in response_lower:
            is_mentioned = True
        elif len(words) >= 2 and " ".join(words[:2]) in response_lower:
            is_mentioned = True
        elif len(words) == 1 and words[0] in response_lower:
            is_mentioned = True
            
        if is_mentioned:
            img_path = p.get("image_local_path", "")
            if img_path and os.path.exists(img_path) and img_path not in image_paths:
                image_paths.append(img_path)

    # Fallback: if no products matched by name but the user initiated an image search,
    # default to showing the top match image.
    if not image_paths and products and image_path:
        top_prod = products[0]
        img_path = top_prod.get("image_local_path", "")
        if img_path and os.path.exists(img_path):
            image_paths.append(img_path)

    t_end = time.perf_counter()
    total_latency = t_end - t_start

    return {
        "text":   response.text,
        "images": image_paths,
        "latency": total_latency
    }