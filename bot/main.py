import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.message import handle_message, handle_callback

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Something went wrong on my end. Try again or rephrase?")
        except Exception:
            pass


def _app_url(telegram_id: int) -> str:
    base = os.getenv("APP_URL", "").rstrip("/")
    return f"{base}?user={telegram_id}"


def _help_text(lang: str, telegram_id: int = 0) -> str:
    if telegram_id:
        url = _app_url(telegram_id)
        # MarkdownV2: escape special chars in URL (only = and ? need escaping outside link syntax)
        link = f"[Content Palace]({url})"
    else:
        link = "Content Palace"
    if lang == "ru":
        return (
            f"Готово\! 🎬📚\n\n"
            f"Просто напиши что смотришь, читаешь или слушаешь — я запишу и спрошу что понравилось\.\n\n"
            f"*Попробуй:*\n"
            f"• посмотрела Дюну\n"
            f"• начала читать Сапиенс\n"
            f"• хочу посмотреть Паразиты\n"
            f"• закончила Во все тяжкие, обожаю\n\n"
            f"*Добавить заметку:*\n"
            f"• добавить к \\[название\\] текст\n\n"
            f"*Команды:*\n"
            f"• удали \\[название\\] — удалить запись\n"
            f"• оцени \\[название\\] loved/average/regret — обновить оценку\n"
            f"• /lang — сменить язык\n"
            f"• /help — показать эту подсказку\n\n"
            f"📱 Открыть библиотеку: {link}\n\n"
            f"_Если я запутаюсь — напиши /start и начнём заново\._"
        )
    else:
        return (
            f"All set\! 🎬📚\n\n"
            f"Just tell me what you're watching, reading, or listening to — I'll log it and ask what you thought\.\n\n"
            f"*Try it:*\n"
            f"• watched Dune\n"
            f"• started reading Sapiens\n"
            f"• want to watch Parasite\n"
            f"• finished Breaking Bad, loved it\n\n"
            f"*Add a note later:*\n"
            f"• add to \\[title\\] your note\n\n"
            f"*Commands:*\n"
            f"• delete \\[title\\] — remove an entry\n"
            f"• rate \\[title\\] loved/average/regret — update your rating\n"
            f"• /lang — change language\n"
            f"• /help — show this message again\n\n"
            f"📱 View your library: {link}\n\n"
            f"_If I get confused, just send /start to reset\\._"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.database import get_user, set_session_state
    telegram_id = update.effective_user.id
    set_session_state(telegram_id, "idle")

    user = get_user(telegram_id)
    if user:
        lang = user.get("lang", "en")
        url = _app_url(telegram_id)
        if lang == "ru":
            await update.message.reply_text(
                f"👋 Снова привет\! Напиши что смотришь или читаешь\.\n\n📱 [Content Palace]({url})",
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                f"👋 Welcome back\! Tell me what you're watching or reading\.\n\n📱 [Content Palace]({url})",
                parse_mode="MarkdownV2"
            )
        return

    # New user — ask language first
    keyboard = [[
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
    ]]
    await update.message.reply_text(
        "👋 Welcome to Content Palace!\n\nChoose your language:\nВыбери язык:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from services.database import get_user
    telegram_id = update.effective_user.id
    user = get_user(telegram_id)
    lang = user.get("lang", "en") if user else "en"
    await update.message.reply_text(_help_text(lang, telegram_id), parse_mode="MarkdownV2")


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow changing language with /lang"""
    keyboard = [[
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
    ]]
    await update.message.reply_text(
        "Choose language / Выбери язык:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle set_lang callback — registered here so it fires before handle_callback."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("set_lang:"):
        # Pass to main callback handler
        await handle_callback(update, context)
        return

    _, lang = data.split(":")
    telegram_id = update.effective_user.id
    name = update.effective_user.first_name or update.effective_user.username or "User"

    from services.database import get_or_create_user, update_user, get_user
    existing = get_user(telegram_id)
    if existing:
        update_user(telegram_id, {"lang": lang})
    else:
        get_or_create_user(telegram_id, name, lang)

    welcome = _help_text(lang, telegram_id)
    await query.edit_message_text(welcome, parse_mode="MarkdownV2")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lang", lang_command))
    # set_lang must be handled before the generic handle_callback
    app.add_handler(CallbackQueryHandler(handle_set_lang, pattern="^set_lang:"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Content Palace bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
