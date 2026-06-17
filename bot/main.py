import os
import logging
import tempfile
import time
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from bot.router import (
    State,
    get_state,
    set_state,
    reset_state,
    get_conv_id,
    set_conv_id,
    reset_conv_id,
    get_rating_score,
    set_rating_score,
    reset_rating_score,
)
from bot.handlers.product_info import handle_product_info
from bot.handlers.payment_policy import handle_payment
from bot.handlers.delivery_status import handle_delivery

from bot.utils.db import (
    create_conversation,
    log_message,
    save_rating,
    end_conversation,
)
from bot.utils.sentiment import analyze_sentiment

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 500


def sanitize(text: str) -> str:
    text = text.strip()
    text = "".join(c for c in text if c.isprintable())
    return text[:MAX_INPUT_LENGTH]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Products",      callback_data="menu_product")],
        [InlineKeyboardButton("💳 Payment",       callback_data="menu_payment")],
        [InlineKeyboardButton("🚚 Order Tracking", callback_data="menu_delivery")],
        [InlineKeyboardButton("🏁 End Conversation", callback_data="menu_end")],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_back")]
    ])


def rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 ⭐", callback_data="rate_1"),
            InlineKeyboardButton("2 ⭐", callback_data="rate_2"),
            InlineKeyboardButton("3 ⭐", callback_data="rate_3"),
            InlineKeyboardButton("4 ⭐", callback_data="rate_4"),
            InlineKeyboardButton("5 ⭐", callback_data="rate_5"),
        ]
    ])


def skip_feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Skip ⏩", callback_data="rate_skip")]
    ])


def get_or_create_session(chat_id: int) -> str:
    conv_id = get_conv_id(chat_id)
    if not conv_id:
        conv_id = create_conversation(str(chat_id))
        set_conv_id(chat_id, conv_id)
    return conv_id


async def send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reset_state(chat_id)
    
    # End any previously active conversation session
    prev_conv = get_conv_id(chat_id)
    if prev_conv:
        end_conversation(prev_conv)
        reset_conv_id(chat_id)
        reset_rating_score(chat_id)

    conv_id = get_or_create_session(chat_id)
    reply_text = "👋 Welcome to *Nappa Milano* Customer Service!\n\nHow can we help you today?"
    await update.message.reply_text(
        reply_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    log_message(conv_id, "assistant", reply_text)


async def process_rating_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE, score: int = None, feedback: str = None):
    chat_id = update.effective_chat.id
    conv_id = get_conv_id(chat_id)

    if not conv_id:
        conv_id = get_or_create_session(chat_id)

    if score is None:
        score = get_rating_score(chat_id) or 5

    sentiment = analyze_sentiment(feedback, score)
    save_rating(conv_id, score, feedback, sentiment)
    end_conversation(conv_id)

    reset_state(chat_id)
    reset_conv_id(chat_id)
    reset_rating_score(chat_id)

    thank_you_text = "Thank you! Your feedback has been recorded. Have a great day!\nClick /start if you want to start a new conversation."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(thank_you_text)
    else:
        await update.message.reply_text(thank_you_text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    data    = query.data

    if data == "menu_product":
        set_state(chat_id, State.PRODUCT_INFO)
        await query.edit_message_text(
            "📦 *Product Information*\n\nType your question about our products, or send a photo of a shoe you'd like to find.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    elif data == "menu_payment":
        set_state(chat_id, State.PAYMENT)
        await query.edit_message_text(
            "💳 *Payment*\n\nType your question about payment methods or how to complete a payment.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    elif data == "menu_delivery":
        set_state(chat_id, State.DELIVERY)
        await query.edit_message_text(
            "🚚 *Order Tracking*\n\nPlease provide your full name or the phone number used when placing your order.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )

    elif data == "menu_back":
        reset_state(chat_id)
        await query.edit_message_text(
            "How can we help you today?",
            reply_markup=main_menu_keyboard()
        )

    elif data == "menu_end":
        set_state(chat_id, State.RATING_SCORE)
        await query.edit_message_text(
            "🏁 *End Conversation*\n\nThank you for using Nappa Milano support. "
            "How satisfied are you with our Customer Service AI?",
            parse_mode="Markdown",
            reply_markup=rating_keyboard()
        )

    elif data.startswith("rate_"):
        score_str = data.split("_")[1]
        if score_str == "skip":
            await process_rating_and_finish(update, context, score=None, feedback=None)
        else:
            score = int(score_str)
            set_rating_score(chat_id, score)
            set_state(chat_id, State.RATING_FEEDBACK)
            await query.edit_message_text(
                f"You rated us {score} ⭐.\n\nDo you have any comments or suggestions for us? "
                "Feel free to type your feedback, or click Skip below.",
                reply_markup=skip_feedback_keyboard()
            )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    text    = sanitize(update.message.text)

    if state == State.RATING_FEEDBACK:
        await process_rating_and_finish(update, context, feedback=text)
        return

    if state == State.RATING_SCORE:
        await update.message.reply_text("Please use the rating buttons below to select a score (1-5).")
        return

    conv_id = get_or_create_session(chat_id)
    log_message(conv_id, "user", text)

    if state == State.IDLE:
        reply_text = "Please select a topic first:"
        await update.message.reply_text(
            reply_text,
            reply_markup=main_menu_keyboard()
        )
        log_message(conv_id, "assistant", reply_text)
        return

    await send_typing(update, context)

    if state == State.PRODUCT_INFO:
        result = handle_product_info(text)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        log_message(conv_id, "assistant", result["text"], latency=result.get("latency"))
        for img_path in result["images"]:
            try:
                await update.message.reply_photo(open(img_path, "rb"))
            except Exception as e:
                logger.warning(f"Failed to send image {img_path}: {e}")

    elif state == State.PAYMENT:
        t_start = time.perf_counter()
        result = handle_payment(text)
        latency = time.perf_counter() - t_start
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        log_message(conv_id, "assistant", result["text"], latency=latency)

    elif state == State.DELIVERY:
        t_start = time.perf_counter()
        result = handle_delivery(text)
        latency = time.perf_counter() - t_start
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        log_message(conv_id, "assistant", result["text"], latency=latency)
        logger.info(f"[delivery] sql: {result.get('sql')}")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)

    if state in (State.RATING_SCORE, State.RATING_FEEDBACK):
        await update.message.reply_text("Please finish the rating process first before sending images.")
        return

    if state != State.PRODUCT_INFO:
        await update.message.reply_text(
            "Photo search is only available for product queries.\nPlease select *Products* from the menu first.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return

    conv_id = get_or_create_session(chat_id)
    log_message(conv_id, "user", "[Photo Search]")

    await send_typing(update, context)

    caption    = sanitize(update.message.caption or "")
    photo_file = await update.message.photo[-1].get_file()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await photo_file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        result = handle_product_info(caption or "find a product similar to this", image_path=tmp_path)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        log_message(conv_id, "assistant", result["text"], latency=result.get("latency"))
        for img_path in result["images"]:
            try:
                await update.message.reply_photo(open(img_path, "rb"))
            except Exception as e:
                logger.warning(f"Failed to send image {img_path}: {e}")
    finally:
        os.unlink(tmp_path)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()