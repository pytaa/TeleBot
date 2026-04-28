import os
import logging
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

# --- STATE UNTUK CONVERSATION ---
# Tambahkan REG_USER untuk menampung input username dari Admin
REG_WITEL, REG_USER, SET_HARI = range(3)

# --- KONFIGURASI ---
raw_admin = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in raw_admin.split(",") if i.strip()]

# --- KONEKSI GOOGLE SHEETS ---
def connect_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    return client.open_by_key(spreadsheet_id)

# ==========================================
# 1. REGISTRASI / EDIT PIC (ADD & EDIT)
# ==========================================
async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 <b>Mode Registrasi/Edit PIC</b>\n\n"
        "Silakan ketik <b>Nama Witel/Unit</b> sesuai database:\n"
        "<i>(Contoh: Makassar, Witel Papua, atau ED)</i>",
        parse_mode="HTML"
    )
    return REG_WITEL

async def reg_witel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    witel_input = update.message.text.strip()
    context.user_data['selected_witel'] = witel_input
    user_id = update.effective_user.id

    # CEK: Jika Admin, minta input username manual (untuk Add/Edit PIC lain)
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            f"Unit: <b>{witel_input}</b>\n\n"
            "Anda masuk sebagai <b>Admin</b>. Silakan ketik <b>Username Telegram PIC</b> (pake @):\n"
            "<i>Contoh: @username_pic atau @evita_vp</i>",
            parse_mode="HTML"
        )
        return REG_USER
    else:
        # Jika User biasa, langsung ambil username mereka sendiri
        user_handle = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        return await proses_simpan_pic(update, context, user_handle)

async def reg_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Menangkap input username yang diketik Admin
    target_username = update.message.text.strip()
    return await proses_simpan_pic(update, context, target_username)

# --- FUNGSI INTERNAL UNTUK UPDATE SPREADSHEET ---
async def proses_simpan_pic(update, context, username_to_save):
    witel_name = context.user_data.get('selected_witel')
    
    try:
        ss = connect_sheets()
        sh_pic = ss.worksheet("PIC_LIST")
        cell = sh_pic.find(witel_name, in_column=1)
        
        if cell:
            sh_pic.update_cell(cell.row, 2, username_to_save)
            await update.message.reply_text(
                f"✅ <b>Berhasil Diperbarui!</b>\n\n"
                f"Unit: <code>{witel_name}</code>\n"
                f"PIC: <code>{username_to_save}</code>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Gagal!</b>\nUnit <b>{witel_name}</b> tidak ditemukan di tab PIC_LIST.\n"
                "Pastikan ejaan sama persis dengan di Spreadsheet."
            )
            
    except Exception as e:
        logging.error(f"Error Update PIC: {e}")
        await update.message.reply_text("⚠️ Terjadi kesalahan saat mengakses Spreadsheet.")
        
    return ConversationHandler.END

# ==========================================
# 2. PENGATURAN HARI KERJA (ADMIN ONLY)
# ==========================================
async def set_hari_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 Maaf, perintah ini hanya untuk Admin.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📅 <b>Pengaturan Hari Kerja Bot</b>\n\n"
        "Masukkan angka hari (0=Senin, 6=Minggu) dipisahkan koma.\n"
        "Contoh: <code>0,1,2,3,4</code> (Senin - Jumat)",
        parse_mode="HTML"
    )
    return SET_HARI

async def set_hari_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_hari = update.message.text.strip()
    try:
        list_hari = [int(h.strip()) for h in input_hari.split(",")]
        context.bot_data['hari_kerja'] = list_hari
        await update.message.reply_text(f"✅ Jadwal diperbarui: <code>{list_hari}</code>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Gunakan format angka. Contoh: 0,1,2")
        return SET_HARI
    return ConversationHandler.END

# ==========================================
# 3. KENDALI & HANDLER
# ==========================================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Aksi dibatalkan.")
    return ConversationHandler.END

def get_admin_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("register", reg_start),
            CommandHandler("sethari", set_hari_start)
        ],
        states={
            REG_WITEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_witel)],
            REG_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_user_admin)],
            SET_HARI: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_hari_save)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )