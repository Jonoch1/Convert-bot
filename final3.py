import os
import re
import subprocess
import threading

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from fastapi import FastAPI
import uvicorn

# ======= Konfigurasi =======
TOKEN = os.getenv("7729313451:AAG3yPmECaxVD6EVyipmtjQxfufPUjl_BQY")
RTMP_BASE_URL = "rtmp://jk1.pull.flve.cc/dream/"

# ======= Install FFmpeg (Render Free container) =======
os.system("apt-get update && apt-get install -y ffmpeg")

# ======= FastAPI Endpoint untuk ping /healthz =======
api = FastAPI()

@api.get("/healthz")
def health_check():
    return {"status": "ok"}

def run_fastapi():
    uvicorn.run(api, host="0.0.0.0", port=10000)

# ======= Utilitas =======
def escape_markdown_v2(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

def extract_stream_key(text: str) -> str:
    match = re.search(r'[rs]\d+_\d+_[a-f0-9]+.*?(?=\s|$)', text)
    return match.group() if match else None

def generate_rtmp_links(stream_key: str):
    if stream_key.startswith('r') or stream_key.startswith('s'):
        cleaned = stream_key[1:]
        return [
            f"rtmp://bcdn5.livcdn.com/live/{cleaned}",
            f"rtmp://pull.cdnsi.com/live/{cleaned}"
        ]
    return []

def check_rtmp_active(rtmp_url: str) -> bool:
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_streams', rtmp_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

def extract_info(text):
    match = re.search(r'R(\d+_\d+)\?auth_key=([\w-]+)', text)
    if not match:
        return None
    stream_id = match.group(1)
    auth_key = match.group(2)
    rtmp_url = f"{RTMP_BASE_URL}{stream_id}?auth_key={auth_key}"
    return rtmp_url, stream_id

# ======= Handler =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Selamat datang!\n\nKirim kode stream dari Canary (stream key atau auth_key) untuk mendapatkan link RTMP dan statusnya."
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'start_check':
        await query.edit_message_text(
            text="📥 Kirimkan kode stream seperti r501_... atau Rxxx_xxx?auth_key=..."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # === Cek auth_key ===
    info = extract_info(text)
    if info:
        rtmp_url, stream_id = info
        is_active = check_rtmp_active(rtmp_url)
        status_text = "✅ Aktif" if is_active else "❌ Tidak Aktif"
        escaped_url = escape_markdown_v2(rtmp_url)

        response = (
            f"*Stream Info :*\n"
            f"• *RTMP URL:*\n```{escaped_url}```\n\n"
            f"• *Status* {status_text}"
        )
        await update.message.reply_text(response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
        return

    # === Cek stream key ===
    stream_key = extract_stream_key(text)
    if stream_key:
        links = generate_rtmp_links(stream_key)
        active_links = [link for link in links if check_rtmp_active(link)]

        selected_url = active_links[0] if active_links else links[0]
        status_text = "✅ Aktif" if active_links else "❌ Tidak Aktif"
        escaped_url = escape_markdown_v2(selected_url)

        response = (
            f"*Stream Info :*\n"
            f"• *RTMP URL:*\n```{escaped_url}```\n\n"
            f"• *Status* {status_text}"
        )
        await update.message.reply_text(response, parse_mode=telegram.constants.ParseMode.MARKDOWN_V2)
        return

    # === Tidak cocok ===
    await update.message.reply_text(
        "❌ Format tidak dikenali. Kirim kode stream Canary atau stream key seperti r501_..."
    )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Perintah tidak dikenal.")

async def set_commands(application):
    commands = [BotCommand("start", "Mulai dan kirim kode stream")]
    await application.bot.set_my_commands(commands)

# ======= Main =======
def main():
    # Jalankan FastAPI background
    threading.Thread(target=run_fastapi).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.post_init = set_commands

    print("🤖 Bot Telegram aktif!")
    app.run_polling()

if __name__ == "__main__":
    main()
