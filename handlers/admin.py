import os
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

JUDUL, DESKRIPSI, LINK = range(3)


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ENTRY
async def tambah_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Kamu tidak punya akses.")
        return ConversationHandler.END

    await update.message.reply_text("📝 Masukkan *judul artikel:*", parse_mode="Markdown")
    return JUDUL


# STEP 1
async def get_judul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["judul"] = update.message.text

    await update.message.reply_text("📄 Masukkan *deskripsi artikel:*", parse_mode="Markdown")
    return DESKRIPSI


# STEP 2
async def get_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["deskripsi"] = update.message.text

    await update.message.reply_text("🔗 Kirim link artikel atau ketik `skip`", parse_mode="Markdown")
    return LINK


# STEP 3
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    link = update.message.text
    if link.lower() != "skip":
        context.user_data["link"] = link
    else:
        context.user_data["link"] = "-"

    judul = context.user_data["judul"]
    deskripsi = context.user_data["deskripsi"]
    link = context.user_data["link"]

    # nanti bisa simpan ke DB / Google Sheets
    hasil = f"""
✅ *Artikel berhasil ditambahkan!*

📌 *Judul:* {judul}
📄 *Deskripsi:* {deskripsi}
🔗 *Link:* {link}
"""

    await update.message.reply_text(hasil, parse_mode="Markdown")

    context.user_data.clear()

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Penambahan artikel dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END


def get_admin_handler():

    conv = ConversationHandler(

        entry_points=[
            CommandHandler(
                "tambah",
                tambah_start,
                filters=filters.ChatType.PRIVATE  # 🔥 hanya DM
            )
        ],

        states={

            JUDUL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_judul)
            ],

            DESKRIPSI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_deskripsi)
            ],

            LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)
            ],
        },

        fallbacks=[CommandHandler("cancel", cancel)]
    )

    return conv
