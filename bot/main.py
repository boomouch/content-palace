import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, filters

from handlers.message import handle_message, handle_callback

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def start(update, context):
    from services.database import set_session_state
    telegram_id = update.effective_user.id
    set_session_state(telegram_id, "idle")
    await update.message.reply_text(
        "👋 Hey! I'm your Content Palace bot.\n\n"
        "Just tell me what you're reading or watching — in your own words.\n\n"
        "Examples:\n"
        "• _started reading Wuthering Heights_\n"
        "• _finished Dune, absolutely loved it_\n"
        "• _want to watch Parasite at some point_\n"
        "• _delete Dune_\n"
        "• _update Dune rating 🔥_",
        parse_mode="Markdown"
    )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Content Palace bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
