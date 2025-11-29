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

# ------------------ LOGGING ------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ------------------ CONFIG ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_DELAY = int(os.getenv("DELETE_DELAY", "300"))  # default 5 minutes (300s)
PORT = int(os.getenv("PORT", "10000"))  # Render uses this


# ------------------ DELETE MESSAGE ------------------
async def delete_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat"], data["msg"])
        logger.info(f"Deleted message {data['msg']} from chat {data['chat']}")
    except Exception as e:
        logger.warning(f"Delete failed: {e}")


# ------------------ MESSAGE HANDLER ------------------
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delay = context.chat_data.get("delay", DEFAULT_DELAY)

    context.job_queue.run_once(
        delete_job,
        delay,
        data={"chat": update.effective_chat.id, "msg": update.effective_message.message_id},
    )


# ------------------ ADMIN CHECK ------------------
async def is_admin(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


# ------------------ /start COMMAND ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delay = context.chat_data.get("delay", DEFAULT_DELAY)
    await update.message.reply_text(
        f"🤖 Auto Delete Bot Active!\n\n⏳ Current delay: {delay}s\n\nUse:\n/delay <seconds>"
    )


# ------------------ /delay COMMAND ------------------
async def delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("❌ Only admins can change delay.")

    if not context.args:
        return await update.message.reply_text("Usage: /delay 60")

    try:
        new_delay = int(context.args[0])
    except:
        return await update.message.reply_text("Invalid number. Example: /delay 120")

    context.chat_data["delay"] = new_delay
    await update.message.reply_text(f"✔ Delay updated to {new_delay} seconds!")


# ------------------ WEB SERVER FOR RENDER ------------------
async def homepage(request):
    return web.Response(text="🔥 Auto Delete Bot Running!")


async def web_server():
    app = web.Application()
    app.router.add_get("/", homepage)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"🌍 Web server running on port {PORT}")


# ------------------ MAIN ASYNC ENTRY ------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("delay", delay))
    app.add_handler(MessageHandler(filters.ALL, on_message))

    asyncio.create_task(app.run_polling())  # run bot in background
    await web_server()  # run web server

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
