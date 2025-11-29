import os
import logging
import asyncio
from aiohttp import web

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ---------- LOGGING ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YAHAN_TOKEN_DAAL_DE-TEMP")
DEFAULT_DELETE_DELAY = int(os.getenv("DELETE_DELAY", "300"))  # 300 sec = 5 min

PORT = int(os.getenv("PORT", "10000"))  # Render web service ke liye


# ---------- TELEGRAM PART ----------

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Delete nahi ho paya (msg {message_id}, chat {chat_id}): {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    chat_id = chat.id
    message_id = message.message_id

    delay = context.chat_data.get("delay", DEFAULT_DELETE_DELAY)

    logger.info(
        f"Scheduling delete for msg {message_id} in chat {chat_id} after {delay} seconds"
    )

    context.job_queue.run_once(
        delete_message_job,
        when=delay,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"delete_{chat_id}_{message_id}",
    )


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if chat is None or user is None:
        return False

    if chat.type == "private":
        return True

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"Admin check failed: {e}")
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_delay = context.chat_data.get("delay", DEFAULT_DELETE_DELAY)
    text = (
        "👋 Namaste! Main auto-delete bot hoon.\n\n"
        "Jo bhi message group me aayega, main kuch time baad delete kar dunga.\n\n"
        f"Current delete delay: <b>{chat_delay} seconds</b>\n\n"
        "Commands:\n"
        "/delay – current delay dekho\n"
        "/delay <seconds> – delay change karo (sirf admins)\n\n"
        "Example:\n"
        "<code>/delay 60</code> → 1 minute baad delete\n"
        "<code>/delay 300</code> → 5 minute baad delete"
    )

    await update.effective_message.reply_text(text, parse_mode="HTML")


async def delay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    if len(context.args) == 0:
        current_delay = context.chat_data.get("delay", DEFAULT_DELETE_DELAY)
        await message.reply_text(
            f"⌛ Current delete delay: {current_delay} seconds.\n\n"
            "Naya delay set karne ke liye:\n"
            "/delay 60  (1 min)\n"
            "/delay 300 (5 min)"
        )
        return

    if not await is_admin(update, context):
        await message.reply_text("❌ Sirf group admins delay change kar sakte hain.")
        return

    arg = context.args[0]
    try:
        new_delay = int(arg)
        if new_delay < 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Galat value. Example: /delay 60  ya  /delay 300")
        return

    if new_delay > 86400:
        await message.reply_text("❌ Max 86400 seconds (24 ghante) tak allowed hai.")
        return

    context.chat_data["delay"] = new_delay
    await message.reply_text(
        f"✅ Delete delay ab <b>{new_delay} seconds</b> ho gaya.",
        parse_mode="HTML",
    )
    logger.info(f"Chat {chat.id} delay updated to {new_delay} seconds")


async def on_startup(app):
    logger.info("Bot started and ready to auto-delete messages!")


def build_telegram_app():
    if BOT_TOKEN == "YAHAN_TOKEN_DAAL-DE-TEMP":
        raise RuntimeError("BOT_TOKEN set kar pehle! Environment variable me.")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("delay", delay_command))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    return app


# ---------- DUMMY WEB SERVER (Render ke liye) ----------

async def handle_root(request):
    return web.Response(text="Telegram auto-delete bot running 🤖")


async def start_web_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server running on port {PORT}")


# ---------- MAIN (donon ko parallel chalao) ----------

async def main_async():
    tg_app = build_telegram_app()

    loop = asyncio.get_running_loop()
    # Telegram bot polling ko ek alag task me chalao
    bot_task = loop.create_task(tg_app.run_polling(stop_signals=None))

    # Web server start karo
    await start_web_app()

    # Dono parallel chalenge
    await bot_task


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
