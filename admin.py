import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

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


# --- ENTRY ---
async def tambah_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Kamu tidak punya akses.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 Masukkan *judul artikel:*",
        parse_mode="Markdown"
    )
    return JUDUL


# --- STEP 1: JUDUL ---
async def get_judul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["judul"] = update.message.text

    await update.message.reply_text(
        "📅 Masukkan *deadline* (format: YYYY-MM-DD)",
        parse_mode="Markdown"
    )
    return DEADLINE


# --- STEP 2: DEADLINE ---
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["deadline"] = update.message.text

    await update.message.reply_text(
        "👤 Masukkan *username penulis* (contoh: @evitaaa)",
        parse_mode="Markdown"
    )

    return PENULIS


# --- STEP 3: PENULIS + SIMPAN ---
async def get_penulis(update: Update, context: ContextTypes.DEFAULT_TYPE):

    penulis = update.message.text.strip()
    judul = context.user_data.get("judul")
    deadline = context.user_data.get("deadline")

    # Auto tambah @ jika belum ada
    if not penulis.startswith("@"):
        penulis = f"@{penulis}"

    try:
        sh = connect_sheets()
        records = sh.get_all_records()

        # AUTO ID
        new_id = len(records) + 1

        # SIMPAN KE SHEETS
        sh.append_row([
            new_id,        # Kolom A: ID
            "",            # Kolom B: chat_id (opsional)
            penulis,       # Kolom C: Penulis
            judul,         # Kolom D: Judul
            deadline,      # Kolom E: Deadline
            "pending"      # Kolom F: Status
        ])

        await update.message.reply_text(
            f"""✅ *Artikel berhasil ditambahkan!*

🆔 ID: {new_id}
👤 Penulis: {penulis}
📝 Judul: {judul}
📅 Deadline: {deadline}
📌 Status: pending
""",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text("❌ Gagal menyimpan ke spreadsheet.")
        print("ERROR:", e)

    context.user_data.clear()
    return ConversationHandler.END


# --- CANCEL ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Penambahan artikel dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END


# --- HANDLER ---
def get_admin_handler():

    conv = ConversationHandler(

        entry_points=[
            CommandHandler(
                "tambah",
                tambah_start,
                filters=filters.ChatType.PRIVATE  # hanya DM
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

        fallbacks=[CommandHandler("cancel", cancel)]
    )

    return conv