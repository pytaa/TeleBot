import os
import pytz
import datetime
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv

# 1. LOAD DOTENV DULUAN
load_dotenv()

# 2. BARU IMPORT DARI FILE LAIN
from admin import get_admin_handler, connect_sheets

# --- KONFIGURASI ---
try:
    GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))
except (ValueError, TypeError):
    print("❌ ERROR: GROUP_CHAT_ID di .env tidak ditemukan atau bukan angka!")
    GROUP_CHAT_ID = 0

TIMEZONE = pytz.timezone('Asia/Makassar')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FUNGSI LIST WITEL (Fitur Baru) ---
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        ss = connect_sheets()
        sheet_pic = ss.worksheet("PIC_LIST")
        master_pic = sheet_pic.get_all_records()
        
        if not master_pic:
            pesan = "📭 Daftar PIC masih kosong di Spreadsheet."
        else:
            teks_list = []
            for i, p in enumerate(master_pic, 1):
                witel = p.get('Witel', 'Unit Tanpa Nama')
                username = p.get('Username', '-')
                teks_list.append(f"{i}. <b>{witel}</b> — {username}")
            
            pesan = "📋 <b>DAFTAR UNIT & PIC TERDAFTAR</b>\n\n" + "\n".join(teks_list)

        if query:
            await query.message.reply_text(pesan, parse_mode="HTML")
        else:
            await update.message.reply_text(pesan, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error pada cmd_list: {e}")
        await update.effective_message.reply_text("⚠️ Gagal mengambil daftar PIC dari Spreadsheet.")

# --- FUNGSI CEK STATUS ---
async def cmd_cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    user_handle = f"@{user.username}" if user.username else user.first_name

    try:
        sudah, belum, tgl = await dapatkan_status_harian()
        is_belum = any(user_handle in b for b in belum)
        
        if is_belum:
            pesan = f"⚠️ <b>Status {tgl}:</b>\nAnda belum submit berita hari ini. Segera lapor ya!"
        else:
            pesan = f"✅ <b>Status {tgl}:</b>\nTerima kasih! Laporan Anda sudah tercatat di sistem."
            
        if query:
            await query.message.reply_text(pesan, parse_mode="HTML")
        else:
            await update.message.reply_text(pesan, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error pada cmd_cek: {e}")
        await update.effective_message.reply_text("⚠️ Gagal mengambil data.")

# --- START MENU DENGAN KEYBOARD ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    chat_type = update.effective_chat.type  # Cek tipe chat (private atau group/supergroup)

    if chat_type == "private":
        # --- MENU KHUSUS DM (Lengkap dengan Register & Set Hari) ---
        keyboard = [
            [
                InlineKeyboardButton("📋 List Witel", callback_data="menu_list"),
            ],
            [
                InlineKeyboardButton("📝 Registrasi PIC", callback_data="menu_reg_info"),
                InlineKeyboardButton("⚙️ Set Hari Kerja", callback_data="menu_sethari_info"),
            ],
        ]
        pesan = (
            f"Halo {user_name}! 🦅\n\n"
            "Ini adalah *Menu Privat* Anda. Di sini Anda bisa mendaftarkan unit "
            "atau mengatur jadwal bot (khusus Admin)."
        )
    else:
        # --- MENU KHUSUS GRUP (Hanya fitur publik) ---
        keyboard = [
            [
                InlineKeyboardButton("📊 Cek Status", callback_data="menu_cek"),
                InlineKeyboardButton("📋 List Witel", callback_data="menu_list"),
            ],
            [
                InlineKeyboardButton("📝 Registrasi PIC (DM)", url=f"https://t.me/{context.bot.username}?start=reg"),
                InlineKeyboardButton("📘 Panduan", callback_data="menu_panduan")
            ]
        ]
        pesan = (
            f"Halo {user_name}! 🦅\n\n"
            "Gunakan tombol di bawah untuk mengecek laporan harian unit Anda."
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(pesan, reply_markup=reply_markup, parse_mode="HTML")

# --- HANDLER CALLBACK ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_cek":
        await cmd_cek(update, context)
    elif query.data == "menu_list":
        await cmd_list(update, context)
    elif query.data == "menu_reg_info":
        await query.message.reply_text("Silakan ketik perintah <b>/register</b> untuk memulai pendaftaran.", parse_mode="HTML")
    elif query.data == "menu_sethari_info":
        await query.message.reply_text("Silakan ketik perintah <b>/sethari</b> untuk mengatur jadwal (Admin Only).", parse_mode="HTML")
    elif query.data == "menu_panduan":
        await query.message.reply_text("Silakan isi Google Form setiap hari sebelum jam 17:00 WITA.")

# --- LOGIKA PENGECEKAN DATA ---
async def dapatkan_status_harian():
    ss = connect_sheets()
    sheet_responses = ss.worksheet("Form Responses 1")
    sheet_pic = ss.worksheet("PIC_LIST")
    
    now = datetime.datetime.now(TIMEZONE)
    today = now.strftime('%d/%m/%Y') 
    
    all_responses = sheet_responses.get_all_values()
    master_pic = sheet_pic.get_all_records()
    
    witel_sudah_isi = []
    for row in all_responses[1:]:
        try:
            timestamp_val = str(row[1]) # Kolom ke-2
            pic_val = str(row[5])       # Kolom ke-6
            if today in timestamp_val:
                witel_sudah_isi.append(pic_val)
        except IndexError:
            continue
            
    sudah, belum = [], []
    for p in master_pic:
        w, u = p.get('Witel'), p.get('Username')
        if w in witel_sudah_isi:
            sudah.append(f"✅ {w}")
        else:
            # Username diletakkan dalam kurung agar bisa di-mention/dilihat
            belum.append(f"❌ {w} ({u})")
            
    return sudah, belum, today

# --- REMINDER FUNCTIONS ---
async def kirim_reminder_pagi(context: ContextTypes.DEFAULT_TYPE):
    pesan = (

        "☀️ <b>MORNING REMINDER: ONE DAY ONE NEWS</b>\n\n"

        "Semangat pagi rekan-rekan PIC! 🦅\n"

        "Mari mulai mencari konten berita menarik hari ini untuk meningkatkan eksposur unit kita.\n\n"

        "🔗 <i>Jangan lupa submit melalui Google Form ya!</i>"

    )
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=pesan, parse_mode="HTML")

async def kirim_reminder_siang(context: ContextTypes.DEFAULT_TYPE):
    try:
        sudah, belum, tgl = await dapatkan_status_harian()
        pesan = f"🕒 <b>UPDATE STATUS SIANG ({tgl})</b>\n\nBelum Submit:\n" + "\n".join(belum)
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=pesan, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error Siang: {e}")

async def kirim_rekap_sore(context: ContextTypes.DEFAULT_TYPE):
    try:
        sudah, belum, tgl = await dapatkan_status_harian()
        teks = f"📊 <b>REKAP FINAL ({tgl})</b>\n\nSudah:\n" + "\n".join(sudah)
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=teks, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error Sore: {e}")

# --- MAIN ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.bot_data['hari_kerja'] = [0, 1, 2, 3, 4] 
    
    # Daftarkan semua handler
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cek", cmd_cek))
    app.add_handler(CommandHandler("list", cmd_list)) # PENTING: Tambahkan ini
    app.add_handler(get_admin_handler())
    app.add_handler(CallbackQueryHandler(button_handler))

    job_queue = app.job_queue
    job_queue.run_once(kirim_reminder_pagi, when=5)
    job_queue.run_once(kirim_reminder_siang, when=10)
    job_queue.run_once(kirim_rekap_sore, when=15)

    print("🚀 Bot sedang berjalan. Cek grup Telegram...")
    app.run_polling()