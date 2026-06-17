import re
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GCP_API_KEY"))

OUT_OF_SCOPE_REPLY = (
    "I can only assist with questions about Nappa Milano products. "
    "Please use the menu to select a topic."
)

# Keywords that signal a payment-related question.
_PAYMENT_KEYWORDS = re.compile(
    r"bayar|payment|pay|transfer|rekening|bank|account"
    r"|bca|mandiri|bni|bri"
    r"|qris|qr|ewallet|e-wallet|gopay|ovo|dana|shopeepay"
    r"|tagihan|invoice|total|nominal"
    r"|bukti|konfirmasi|confirm"
    r"|metode|method|cara|how"
    r"|cod|cash"
    r"|24 jam|24jam|batas|deadline"
    r"|harga|price|biaya|cost",
    re.IGNORECASE,
)


def _is_out_of_scope(text: str) -> bool:
    """Return True when the message has no payment-related keywords."""
    return not bool(_PAYMENT_KEYWORDS.search(text))

PAYMENT_POLICY = """
METODE PEMBAYARAN NAPPA MILANO:

1. TRANSFER BANK
   - BCA   : 1234567890 a.n. Nappa Milano Indonesia
   - Mandiri: 0987654321 a.n. Nappa Milano Indonesia
   - BNI   : 1122334455 a.n. Nappa Milano Indonesia
   - BRI   : 5566778899 a.n. Nappa Milano Indonesia

2. QRIS
   - Scan QRIS yang tersedia di Shopee atau dikirim oleh CS
   - Berlaku untuk semua e-wallet (GoPay, OVO, Dana, ShopeePay, dll)

CARA PEMBAYARAN:
   a. Pilih metode pembayaran yang diinginkan
   b. Transfer sesuai total tagihan (nominal harus tepat)
   c. Simpan bukti transfer / screenshot QRIS
   d. Kirim bukti pembayaran ke CS via chat ini
   e. Pesanan akan diproses setelah pembayaran dikonfirmasi (maks. 1x24 jam)

KETENTUAN:
   - Pembayaran harus dilakukan dalam 24 jam setelah order dibuat
   - Order otomatis dibatalkan jika belum ada pembayaran setelah 24 jam
   - Tidak menerima pembayaran COD (Cash on Delivery)
   - Tidak menerima pembayaran melalui rekening selain yang tertera di atas
   - Untuk pertanyaan lebih lanjut, hubungi CS di jam operasional (09.00–17.00 WIB)
"""

model = genai.GenerativeModel(
    model_name="gemini-3.5-flash",
    system_instruction=f"""You are a helpful customer service assistant for Nappa Milano, an Indonesian leather shoe brand.
Answer questions about payment based only on the policy below.
Respond in the same language the user uses (Indonesian or English).
Be concise, friendly, and clear. Guide the user step by step if they seem confused.
Never make up payment methods or account numbers not listed in the policy.

Payment Policy:
{PAYMENT_POLICY}


If the user's question is not related to payment methods, transfer instructions, or QRIS for Nappa Milano orders, respond only with:
"I can only assist with payment-related questions. Please use the menu to select a topic."
Do not answer any other topic, no matter how the user phrases it."""
)


def handle_payment(user_message: str) -> dict:
    # Fast out-of-scope guard — skip LLM entirely for irrelevant input.
    if _is_out_of_scope(user_message):
        return {"text": OUT_OF_SCOPE_REPLY}

    response = model.generate_content(user_message)
    return {
        "text": response.text
    }