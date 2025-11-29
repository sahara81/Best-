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

# ------------- LOGGING -------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ------------- CONFIG -------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_DELAY = int(os.getenv("DELETE_DELAY", "300"))
PORT = int(os.getenv("PORT", "10000"))


# ------------- JOB: MESSAGE DELETE -------------
async def delete_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    chat_id = data["chat_id"]
    msg_id = data["msg_id"]
    try:
        await context.bot.delete_message(chat_id, msg_id)
        logger.info(f"Deleted message {msg_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Delete failed: {e}")


# ------------- MESSAGE HANDLER -------------
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg:
        return

    delay = context.chat_data.get("delay", DEFAULT_DELAY)

    context.job_queue.run_once(
        delete_job,
        delay,
        data={"chat_id": chat.id, "msg_id": msg.message_id},
    )


# ------------- ADMIN CHECK -------------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")


# ------------- /start -------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delay = context.chat_data.get("delay", DEFAULT_DELAY)
    await update.effective_message.reply_text(
        f"🤖 Auto Delete Bot ON!\n\n⏳ Current delay: {delay} seconds\n\n"
        "Delay change karne ke liye:\n/delay <seconds>\n\n"
        "Example: /delay 60  ya  /delay 300"
    )


# ------------- /delay -------------
async def delay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if not await is_admin(update, context):
        return await msg.reply_text("❌ Sirf admins delay change kar sakte hain.")

    if not context.args:
        current = context.chat_data.get("delay", DEFAULT_DELAY)
        return await msg.reply_text(
            f"⌛ Current delay: {current} seconds\nExample: /delay 60"
        )

    try:
        value = int(context.args[0])
        if value < 0:
            raise ValueError
    except ValueError:
        return await msg.reply_text("❌ Galat value. Example: /delay 120")

    context.chat_data["delay"] = value
    await msg.reply_text(f"✅ Delete delay ab {value} seconds ho gaya.")


# ------------- WEB SERVER (Render ke liye) -------------
async def handle_root(request):
    return web.Response(text="🔥 Telegram auto-delete bot running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌍 Web server running on port {PORT}")


# ------------- BOT SETUP (NO run_polling) -------------
async def setup_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("delay", delay_cmd))
    application.add_handler(MessageHandler(filters.ALL, on_message))

    # yaha sirf initialize/start/polling karenge, koi run_polling nahi
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    logger.info("🤖 Telegram bot polling started.")
    return application


# ------------- MAIN -------------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var set nahi hai.")

    # bot + web server ko same loop me chalao
    await setup_bot()
    await start_web_server()

    # process ko zinda rakhne ke liye
    stop = asyncio.Event()
    await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())
