<<<<<<< HEAD
import os
import logging
import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# 1. KONFIGURASI & LOGGING
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
SHEET_NAME = os.getenv("SPREADSHEET_NAME")

# Logging (Simpan Riwayat Push Message)
logging.basicConfig(
    format ='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level = logging.INFO,         
    handlers = [
        logging.FileHandler("bot.log"), # Simpan log ke file bot.log
        logging.StreamHandler()         # Tampilkan log di console
    ] 
)
logger = logging.getLogger(__name__)

# 2. FUNGSI KONEKSI GOOGLE SHEETS
def connect_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"] 
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# 3. MENGIRIM REMINDER KE GRUP
async def kirim_reminder_grup(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Memulai pengecekan tugas...")

    try:
        sh = connect_sheets()
        records = sh.get_all_records()

        count_sent = 0

        for row in records:
            if str(row['status']).lower() == 'pending':
                # Mengambil data dari Google Sheets
                task_id = row['id']
                penulis = row['penulis']
                judul = row['judul']
                deadline = row['deadline']

                # Pesan reminder yang akan dikirim ke grup
                pesan = (
                    f"📢 <b>REMINDER ARTIKEL</b>\n"
                    f"Halo {penulis}, mohon segera submit ya!\n\n"
                    f"📝 <b>Judul:</b> {judul}\n"
                    f"⏰ <b>Deadline:</b> {deadline}\n\n"
                    f"<i>Klik tombol di bawah untuk konfirmasi jika sudah submit!:</i>"
                )
                
                # Menyederhanakan judul panjang untuk callback data
                judul_pendek = (judul[:30] + '..') if len(judul) > 30 else judul

                # Masukkan judul yang sudah dipendekkan ke tombol
                callback_data = f"done_{task_id}_{judul_pendek}"

                # Tombol konfirmasi sudah submit
                keyboard = [[InlineKeyboardButton("✅ Sudah Submit", callback_data = callback_data)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Mengirim pesan dengan parse_mode HTML
                await context.bot.send_message(
                    chat_id = GROUP_CHAT_ID,
                    text = pesan,
                    reply_markup = reply_markup,
                    parse_mode = "HTML"
                )
                count_sent += 1
        
        if count_sent > 0:
            logger.info(f"Selesai. Mengirim {count_sent} reminder.")
        else:
            logger.info("Tidak ada tugas pending.")
            await context.bot.send_message(
                chat_id = GROUP_CHAT_ID,
                text = "🎉 Semua artikel sudah disubmit! Tidak ada reminder yang dikirim."
            )

    except Exception as e:
        logger.error(f"[ERROR] Gagal mengirim reminder: {e}")

# 4. HANDLER TOMBOL KONFIRMASI SUDAH SUBMIT
async def tombol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_klik = query.from_user.username or query.from_user.first_name

    await query.answer()

    data = query.data
    if data.startswith("done_"):
        try:
            # Mengambil ID dari data tombol
            task_id_target = data.split("_")[1]
            task_title_target = "_".join(data.split("_")[2:])  # Menggabungkan semua bagian setelah ID

            print(f"Tombol diklik! Mencari ID: {task_id_target}...")

            sh = connect_sheets()

            # Mecari baris pada kolom 'id' yang sesuai dengan ID tugas
            cell = sh.find(task_id_target, in_column = 1)

            if cell is None:
                print(f"❌ Gagal: ID {task_id_target} tidak ditemukan di kolom A.")
                await query.message.reply_text(f"⚠️ Gagal: ID {task_id_target} tidak ditemukan di Spreadsheet. Cek datanya.")
                return

            judul_asli = sh.cell(cell.row, 4).value  # Kolom 4 = Kolom D (judul)

            # Update status di Spreadsheet menjadi "Done"
            sh.update_cell(cell.row, 6, "done")         # Kolom 6 = Kolom F (status)

            print(f"✅ Sukses: Status Baris {cell.row} diubah menjadi 'done'")

            # Mengatur zona waktu ke WITA
            tz_wita = pytz.timezone('Asia/Makassar')
            waktu_sekarang = datetime.datetime.now(tz_wita)
            waktu_format = waktu_sekarang.strftime('%d-%m-%Y %H:%M WITA')

            # Mengirim pesan konfirmasi ke grup
            pesan_baru = (
                f"✅ <b>SUDAH DISUBMIT!</b>\n\n"
                f"📝 <b>Judul:</b> {judul_asli}\n"
                f"👤 Dikonfirmasi oleh: @{user_klik}\n"
                f"🕒 Waktu: {waktu_format}"
            )

            try:
                await query.edit_message_text(
                    text = pesan_baru, 
                    parse_mode = "HTML"
                    )
            except Exception:
                await query.message.reply_text(f"✅ Sudah submit! Namun gagal update pesan di grup. Cek log untuk detail.")
        
        except Exception as e:
            print(f"❌ Gagal memproses tombol: {e}")
            await query.message.reply_text("⚠️ Terjadi kesalahan saat update database.")

    # ==== MENU CALLBACK ====
    elif data == "menu_status":
        await cmd_status(update, context)

    elif data == "menu_list":
        await cmd_list(update, context)

    elif data == "menu_petunjuk":
        await cmd_petunjuk(update, context)

    elif data == "menu_panduan":
        await cmd_panduan(update, context)


# 5. CEK STATUS PENDING
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sh = connect_sheets()
    records = sh.get_all_records()

    data = [
        f"• {r['judul']} ({r['penulis']})"
        for r in records if str(r['status']).lower() == "pending"
    ]

    msg = "📋 <b>LIST ARTIKEL BELUM SUBMIT:</b>\n\n" + "\n".join(data) if data else "🎉 Semua artikel sudah disubmit!"
    
    pesan_masuk = update.message or update.callback_query.message
    await pesan_masuk.reply_text(msg, parse_mode="HTML")

# 6. START MENU
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            InlineKeyboardButton("📋 List", callback_data="menu_list"),
        ],
        [
            InlineKeyboardButton("📖 Petunjuk", callback_data="menu_petunjuk"),
            InlineKeyboardButton("📘 Panduan", callback_data="menu_panduan")
        ]
    ]

    await update.message.reply_text(
        "👋 Selamat datang di Bot Artikel\n\nPilih menu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# 7. LIST SEMUA BERITA (BERDASARKAN STATUS)
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sh = connect_sheets()
    records = sh.get_all_records()

    list_pending = [
        f"⏳ {r['judul']} (oleh {r['penulis']})" 
        for r in records if str(r['status']).lower() == "pending"
    ]
    
    list_done = [
        f"✅ {r['judul']} (oleh {r['penulis']})" 
        for r in records if str(r['status']).lower() == "done"
    ]

    teks_pending = "\n".join(list_pending) if list_pending else "Tidak ada artikel pending."
    teks_done = "\n".join(list_done) if list_done else "Tidak ada artikel yang sudah selesai."

    msg = (
        "📊 <b>REKAP STATUS ARTIKEL</b>\n\n"
        "🔴 <b>BELUM SUBMIT (PENDING):</b>\n"
        f"{teks_pending}\n\n"
        "🟢 <b>SUDAH SUBMIT (DONE):</b>\n"
        f"{teks_done}"
    )
    
    pesan_masuk = update.message or update.callback_query.message
    await pesan_masuk.reply_text(msg, parse_mode="HTML")

# 8. PETUNJUK
async def cmd_petunjuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📖 Gunakan bot ini untuk cek & update artikel."
    
    pesan_masuk = update.message or update.callback_query.message
    await pesan_masuk.reply_text(msg, parse_mode="HTML")

# 9. PANDUAN
async def cmd_panduan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📘 Panduan:\n\n"
        "1. Admin input\n"
        "2. Bot kirim reminder\n"
        "3. Klik tombol submit"
    )
    
    pesan_masuk = update.message or update.callback_query.message
    await pesan_masuk.reply_text(msg, parse_mode="HTML")

# MAIN
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # COMMAND
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("petunjuk", cmd_petunjuk))
    app.add_handler(CommandHandler("panduan", cmd_panduan))

    # CALLBACK
    app.add_handler(CallbackQueryHandler(tombol_handler))

    # JOB
    job_queue = app.job_queue
    job_queue.run_repeating(kirim_reminder_grup, interval=120, first=10)

    print("Bot jalan...")
    app.run_polling()