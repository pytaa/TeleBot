import os
import datetime
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ENV ---
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
SHEET_NAME = os.getenv("SPREADSHEET_NAME")

# --- STATE ---
JUDUL, DEADLINE, PENULIS = range(3)

# --- CEK ADMIN ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- KONEKSI GOOGLE SHEETS ---
def connect_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "service_account.json", scope
    )
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# =========================
# 🚀 START TAMBAH ARTIKEL
# =========================
async def tambah_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # hanya DM
    if update.effective_chat.type != "private":
        return ConversationHandler.END

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Kamu tidak punya akses.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 *Masukkan judul artikel:*",
        parse_mode="Markdown"
    )
    return JUDUL

# =========================
# 📝 STEP 1: JUDUL
# =========================
async def get_judul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["judul"] = update.message.text.strip()

    await update.message.reply_text(
        "📅 *Masukkan deadline* (format: YYYY-MM-DD)",
        parse_mode="Markdown"
    )
    return DEADLINE

# =========================
# 📅 STEP 2: DEADLINE
# =========================
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text.strip()

    # VALIDASI FORMAT TANGGAL
    try:
        datetime.datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Format salah!\nGunakan: YYYY-MM-DD\nContoh: 2026-02-25"
        )
        return DEADLINE

    context.user_data["deadline"] = text

    await update.message.reply_text(
        "👤 *Masukkan username penulis* (contoh: @evitaaa)",
        parse_mode="Markdown"
    )

    return PENULIS

# =========================
# 👤 STEP 3: PENULIS + SIMPAN
# =========================
async def get_penulis(update: Update, context: ContextTypes.DEFAULT_TYPE):

    penulis = update.message.text.strip()
    judul = context.user_data.get("judul")
    deadline = context.user_data.get("deadline")

    # auto @
    if not penulis.startswith("@"):
        penulis = f"@{penulis}"

    try:
        sh = connect_sheets()
        records = sh.get_all_records()

        # 🔥 AUTO ID (LEBIH AMAN)
        if records:
            last_id = int(records[-1]['id'])
            new_id = last_id + 1
        else:
            new_id = 1

        # SIMPAN
        sh.append_row([
            new_id,        # A: ID
            "",            # B: chat_id (optional)
            penulis,       # C: Penulis
            judul,         # D: Judul
            deadline,      # E: Deadline
            "pending"      # F: Status
        ])

        # ✅ FORMAT SAMA SEPERTI REMINDER STYLE
        await update.message.reply_text(
            f"""✅ *ARTIKEL BERHASIL DITAMBAHKAN!*

🆔 *ID:* {new_id}
👤 *Penulis:* {penulis}
📝 *Judul:* {judul}
⏰ *Deadline:* {deadline}
📌 *Status:* pending
""",
            parse_mode="Markdown"
        )

        logger.info(f"Artikel baru ditambahkan: {judul}")

    except Exception as e:
        logger.error(f"Gagal simpan: {e}")
        await update.message.reply_text("❌ Gagal menyimpan ke spreadsheet.")

    context.user_data.clear()
    return ConversationHandler.END

# =========================
# ❌ CANCEL
# =========================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Penambahan artikel dibatalkan.")
    return ConversationHandler.END

# =========================
# 📦 HANDLER
# =========================
def get_admin_handler():

    return ConversationHandler(

        entry_points=[
            CommandHandler(
                "tambah",
                tambah_start,
                filters=filters.ChatType.PRIVATE
            )
        ],

        states={
            JUDUL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_judul)
            ],
            DEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_deadline)
            ],
            PENULIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_penulis)
            ],
        },

        fallbacks=[
            CommandHandler("cancel", cancel)
        ]
    )