import os
import logging
import datetime
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
            
            # Update status di Spreadsheet menjadi "Done"
            sh.update_cell(cell.row, 6, "done")         # Kolom 6 = Kolom F (status)

            print(f"✅ Sukses: Status Baris {cell.row} diubah menjadi 'done'")

            # Mengirim pesan konfirmasi ke grup
            pesan_baru = (
                f"✅ <b>SUDAH DISUBMIT!</b>\n\n"
                f"📝 <b>ID:</b> {task_id_target}\n"
                f"📝 <b>Judul:</b> {task_title_target}\n"
                f"👤 Dikonfirmasi oleh: @{user_klik}\n"
                f"🕒 Waktu: {datetime.datetime.now().strftime('%H:%M WIB')}"
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

# 5. CEK STATUS
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sh = connect_sheets()
        records = sh.get_all_records()
        list_pending = []

        for row in records:
            if str(row['status']).lower() == 'pending':
                list_pending.append(f" {row['judul']} (by {row['penulis']})")
        
        if list_pending:
            msg = "📋 **LIST ARTIKEL BELUM SUBMIT:**\n\n" + "\n".join(list_pending)
        else:
            msg = "🎉 Semua artikel sudah disubmit! Tidak ada tugas pending."

        await update.message.reply_text(msg, parse_mode = "Markdown")

    except Exception as e:
        await update.message.reply_text("Gagal mengambil data.")
        logger.error(f"[ERROR] Gagal mengambil status: {e}")


# MAIN PROGRAM
if __name__ == "__main__":
    # Build aplikasi 
    app = ApplicationBuilder().token(TOKEN).build()

    # Menu Handler 
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(tombol_handler))

    # Setup jadwal pengiriman reminder setiap hari
    job_queue = app.job_queue

    print("Bot Berjalan... Tekan Ctrl+C untuk berhenti.")
