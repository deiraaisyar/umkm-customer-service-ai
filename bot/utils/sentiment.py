import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GCP_API_KEY"))

model = genai.GenerativeModel(
    model_name="gemini-3.5-flash",
    system_instruction=(
        "You are a sentiment analysis classifier. Classify the customer feedback "
        "into exactly one of: Positive, Neutral, Negative. "
        "Output ONLY the category name."
    )
)

def analyze_sentiment(text: str, score: int) -> str:
    """Analyze text sentiment using Gemini, fallback to score-based heuristic if empty/fails."""
    if not text or not text.strip():
        # Score-based fallback
        if score >= 4:
            return "Positive"
        elif score == 3:
            return "Neutral"
        else:
            return "Negative"

    try:
        response = model.generate_content(f"Analyze this feedback: '{text}'")
        sentiment = response.text.strip().capitalize()
        if sentiment in ["Positive", "Neutral", "Negative"]:
            return sentiment
    except Exception:
        pass

    # Fallback in case of API issue or unexpected response
    if score >= 4:
        return "Positive"
    elif score == 3:
        return "Neutral"
    else:
        return "Negative"
