import os
import logging
import tempfile
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

from bot.router import State, get_state, set_state, reset_state
from bot.handlers.product_info import handle_product_info
from bot.handlers.payment_policy import handle_payment
from bot.handlers.delivery_status import handle_delivery

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
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_back")]
    ])


async def send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_state(update.effective_chat.id)
    await update.message.reply_text(
        "👋 Welcome to *Nappa Milano* Customer Service!\n\nHow can we help you today?",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


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


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)
    text    = sanitize(update.message.text)

    if state == State.IDLE:
        await update.message.reply_text(
            "Please select a topic first:",
            reply_markup=main_menu_keyboard()
        )
        return

    await send_typing(update, context)

    if state == State.PRODUCT_INFO:
        result = handle_product_info(text)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        for img_path in result["images"]:
            try:
                await update.message.reply_photo(open(img_path, "rb"))
            except Exception as e:
                logger.warning(f"Failed to send image {img_path}: {e}")

    elif state == State.PAYMENT:
        result = handle_payment(text)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())

    elif state == State.DELIVERY:
        result = handle_delivery(text)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
        logger.info(f"[delivery] sql: {result.get('sql')}")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state   = get_state(chat_id)

    if state != State.PRODUCT_INFO:
        await update.message.reply_text(
            "Photo search is only available for product queries.\nPlease select *Products* from the menu first.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return

    await send_typing(update, context)

    caption    = sanitize(update.message.caption or "")
    photo_file = await update.message.photo[-1].get_file()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await photo_file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        result = handle_product_info(caption or "find a product similar to this", image_path=tmp_path)
        await update.message.reply_text(result["text"], reply_markup=back_keyboard())
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