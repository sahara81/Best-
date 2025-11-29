import os
import logging
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
# BOT_TOKEN ko environment variable me rakhna best hai (Render/Koyeb ke liye):
BOT_TOKEN = os.getenv("BOT_TOKEN", "YAHAN_TOKEN_DAAL_DE-TEMP")

# Default delay in seconds (env se override ho sakta hai)
DEFAULT_DELETE_DELAY = int(os.getenv("DELETE_DELAY", "300"))  # 300 sec = 5 min


# ---------- JOB: MESSAGE DELETE KARNA ----------
async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Delete nahi ho paya (msg {message_id}, chat {chat_id}): {e}")


# ---------- HANDLER: HAR MESSAGE PE DELETE JOB LAGANA ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    chat_id = chat.id
    message_id = message.message_id

    # Per-chat delay: agar chat_data me set hai to woh, warna default
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


# ---------- HELPER: ADMIN CHECK ----------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if chat is None or user is None:
        return False

    # Private chat me user hi malik hai, allowed
    if chat.type == "private":
        return True

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning(f"Admin check failed: {e}")
        return False


# ---------- /start COMMAND ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_delay = context.chat_data.get("delay", DEFAULT_DELETE_DELAY)
    text = (
        "👋 Namaste! Main auto-delete bot hoon.\n\n"
        "Jo bhi message group me aayega, main kuch time baad delete kar dunga.\n\n"
        "Current delete delay: <b>{} seconds</b>\n\n"
        "Commands:\n"
        "/delay – current delay dekho\n"
        "/delay &lt;seconds&gt; – delay change karo (sirf admins)\n\n"
        "Example:\n"
        "<code>/delay 60</code> → 1 minute baad delete\n"
        "<code>/delay 300</code> → 5 minute baad delete"
    ).format(chat_delay)

    await update.effective_message.reply_text(text, parse_mode="HTML")


# ---------- /delay COMMAND ----------
async def delay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    if message is None or chat is None:
        return

    # Agar argument nahi diya -> current delay batao
    if len(context.args) == 0:
        current_delay = context.chat_data.get("delay", DEFAULT_DELETE_DELAY)
        await message.reply_text(
            f"⌛ Current delete delay: {current_delay} seconds.\n\n"
            "Naya delay set karne ke liye:\n"
            "/delay 60  (1 min)\n"
            "/delay 300 (5 min)"
        )
        return

    # Delay change karne ke liye admin check
    if not await is_admin(update, context):
        await message.reply_text("❌ Sirf group admins delay change kar sakte hain.")
        return

    # Argument parse karna
    arg = context.args[0]
    try:
        new_delay = int(arg)
        if new_delay < 0:
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Galat value. Example: /delay 60  ya  /delay 300")
        return

    # Limit thoda reasonable rakhte hain (0–86400 sec = 24h)
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


def main():
    if BOT_TOKEN == "YAHAN_TOKEN_DAAL_DE-TEMP":
        raise RuntimeError("BOT_TOKEN set kar pehle! Environment variable ya code me.")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("delay", delay_command))

    # Sab messages (admins + members + bots)
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
