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
NAPPA MILANO PAYMENT METHODS:

1. BANK TRANSFER
   - BCA   : 1234567890 o.b.o. Nappa Milano Indonesia
   - Mandiri: 0987654321 o.b.o. Nappa Milano Indonesia
   - BNI   : 1122334455 o.b.o. Nappa Milano Indonesia
   - BRI   : 5566778899 o.b.o. Nappa Milano Indonesia

2. QRIS
   - Scan the QRIS code available on Shopee or sent by CS
   - Valid for all e-wallets (GoPay, OVO, Dana, ShopeePay, etc.)

PAYMENT STEPS:
   a. Choose your preferred payment method
   b. Transfer the exact amount of the total bill
   c. Save the payment receipt / QRIS screenshot
   d. Send the payment receipt to CS via this chat
   e. Orders will be processed after payment is confirmed (max. 24 hours)

TERMS & CONDITIONS:
   - Payment must be made within 24 hours after the order is created
   - Orders are automatically cancelled if payment is not received within 24 hours
   - COD (Cash on Delivery) is not supported
   - Payments through accounts other than those listed above are not accepted
   - For further inquiries, contact CS during operational hours (09:00–17:00 WIB)
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