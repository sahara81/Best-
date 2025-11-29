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
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_DELAY = int(os.getenv("DELETE_DELAY", "300"))  # seconds
PORT = int(os.getenv("PORT", "10000"))


# ---------- MESSAGE DELETE (no JobQueue) ----------
async def delete_later(bot, chat_id: int, msg_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, msg_id)
        logger.info(f"Deleted msg {msg_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Delete failed: {e}")


# ---------- MESSAGE HANDLER ----------
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    delay = context.chat_data.get("delay", DEFAULT_DELAY)
    asyncio.create_task(
        delete_later(context.bot, chat.id, msg.message_id, delay)
    )


# ---------- ADMIN CHECK ----------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")


# ---------- /start ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delay = context.chat_data.get("delay", DEFAULT_DELAY)
    await update.effective_message.reply_text(
        f"🤖 Auto Delete Bot ON\n\n"
        f"⏳ Current delay: {delay} sec\n\n"
        "Delay change: /delay <seconds>\n"
        "Example: /delay 10  ya  /delay 300"
    )


# ---------- /delay ----------
async def delay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not await is_admin(update, context):
        return await msg.reply_text("❌ Sirf admins delay change kar sakte hain.")

    if not context.args:
        cur = context.chat_data.get("delay", DEFAULT_DELAY)
        return await msg.reply_text(f"⌛ Current delay: {cur} sec\nExample: /delay 10")

    try:
        value = int(context.args[0])
        if value < 0:
            raise ValueError
    except ValueError:
        return await msg.reply_text("❌ Galat value. Example: /delay 60")

    context.chat_data["delay"] = value
    await msg.reply_text(f"✅ Delay ab {value} seconds ho gaya.")


# ---------- WEB SERVER (Render ke liye) ----------
async def handle_root(request):
    return web.Response(text="🔥 Auto delete bot running")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌍 Web server on port {PORT}")


# ---------- BOT SETUP ----------
async def setup_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var set nahi hai.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("delay", delay_cmd))
    app.add_handler(MessageHandler(filters.ALL, on_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("🤖 Bot polling started.")
    return app


# ---------- MAIN ----------
async def main():
    await setup_bot()
    await start_web_server()

    # process ko zinda rakhne ke liye
    stop = asyncio.Event()
    await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())
