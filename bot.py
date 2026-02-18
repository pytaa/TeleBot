import os
import logging
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# --- 1. KONFIGURASI & LOGGING ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
SHEET_NAME = os.getenv("SPREADSHEET_NAME")

# Logging (Simpan error ke file bot.log)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 2. FUNGSI KONEKSI GOOGLE SHEETS ---
def connect_sheets():
    # Pastikan file json service account ada di folder yang sama
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# --- 3. FITUR UTAMA: KIRIM REMINDER KE GRUP (VERSI HTML) ---
async def kirim_reminder_grup(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Memulai pengecekan tugas...") # Hapus emoji jam pasir
    
    try:
        sh = connect_sheets()
        records = sh.get_all_records()
        
        count_sent = 0

        for row in records:
            # Pastikan status dibaca sebagai string lowercase
            if str(row['status']).lower() == 'pending':
                
                # Ambil data
                task_id = row['id']
                penulis = row['penulis'] 
                judul = row['judul']
                deadline = row['deadline']

                # --- PERBAIKAN DI SINI (Gunakan Format HTML) ---
                # HTML lebih aman untuk username yang ada garis bawah (_)
                pesan = (
                    f"📢 <b>REMINDER ARTIKEL</b>\n"
                    f"Halo {penulis}, mohon segera submit ya!\n\n"
                    f"📝 <b>Judul:</b> {judul}\n"
                    f"📅 <b>Deadline:</b> {deadline}\n\n"
                    f"👇 <i>Klik tombol di bawah jika sudah upload:</i>"
                )

                # Tombol Interaktif
                keyboard = [[InlineKeyboardButton("✅ Sudah Submit", callback_data=f"done_{task_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Kirim ke Grup dengan parse_mode HTML
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=pesan,
                    reply_markup=reply_markup,
                    parse_mode="HTML" # <--- PENTING: GANTI JADI HTML
                )
                count_sent += 1
        
        if count_sent > 0:
            logger.info(f"Selesai. Mengirim {count_sent} reminder.")
        else:
            logger.info("Tidak ada tugas pending.")

    except Exception as e:
        # Hapus emoji silang merah di sini agar Windows tidak crash
        logger.error(f"[ERROR] Gagal kirim reminder: {e}")

# --- 4. FITUR TOMBOL: UPDATE STATUS OTOMATIS ---
# --- UPDATE FUNGSI TOMBOL ---
async def tombol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_klik = query.from_user.username or query.from_user.first_name
    
    # 1. Hilangkan animasi loading di tombol
    await query.answer() 

    data = query.data # Contoh: "done_101"
    
    if data.startswith("done_"):
        try:
            # Ambil ID dari data tombol
            task_id_target = data.split("_")[1] 
            
            print(f"👉 Tombol diklik! Mencari ID: {task_id_target}...") # Debug Terminal

            sh = connect_sheets()
            
            # 2. CARA LEBIH AMAN: Cari ID khusus di Kolom 1 (Kolom A) saja
            # Supaya tidak salah ambil angka yang mirip di kolom lain
            cell = sh.find(task_id_target, in_column=1)
            
            # Jika ID tidak ketemu
            if cell is None:
                print(f"❌ Gagal: ID {task_id_target} tidak ditemukan di Kolom A.")
                await query.message.reply_text(f"⚠️ Gagal: ID {task_id_target} tidak ditemukan di Spreadsheet. Cek datanya.")
                return

            # 3. Update Kolom Status (Kolom F = Indeks 6)
            # Pastikan urutan kolom di Excel: A=1, B=2, C=3, D=4, E=5, F=6 (Status)
            sh.update_cell(cell.row, 6, "done")
            
            print(f"✅ Sukses! Baris {cell.row} kolom 6 diubah jadi 'done'.")
            
            # 4. Ubah Pesan di Telegram
            pesan_baru = (
                f"✅ **SUDAH DISUBMIT!**\n\n"
                f"📝 Tugas ID: {task_id_target}\n"
                f"👤 Dikonfirmasi oleh: @{user_klik}\n"
                f"🕒 Waktu: {datetime.datetime.now().strftime('%H:%M WIB')}"
            )
            # Pakai try-except khusus edit pesan (kadang error kalau pesan terlalu lama)
            try:
                await query.edit_message_text(text=pesan_baru, parse_mode="Markdown")
            except Exception:
                # Jika gagal edit (misal pesan kadaluarsa), kirim pesan baru saja
                await query.message.reply_text(f"✅ Tugas ID {task_id_target} statusnya sudah diupdate jadi DONE!")

        except Exception as e:
            # Tampilkan error lengkap di Terminal
            print(f"❌ ERROR SISTEM: {e}")
            await query.message.reply_text("⚠️ Terjadi kesalahan sistem saat update database.")

# --- 5. FITUR TAMBAHAN: CEK STATUS (/status) ---
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sh = connect_sheets()
        records = sh.get_all_records()
        list_pending = []

        for row in records:
            if str(row['status']).lower() == 'pending':
                list_pending.append(f"• {row['judul']} (by {row['penulis']})")
        
        if list_pending:
            msg = "📋 **LIST ARTIKEL BELUM SUBMIT:**\n\n" + "\n".join(list_pending)
        else:
            msg = "🎉 **Luar biasa!** Semua artikel sudah selesai."

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text("Gagal mengambil data.")
        logger.error(e)

# --- MAIN PROGRAM ---
if __name__ == '__main__':
    # Build Aplikasi
    app = ApplicationBuilder().token(TOKEN).build()

    # Daftarkan Handler
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(tombol_handler))

    # Setup JobQueue (Penjadwal)
    job_queue = app.job_queue
    
    print("Bot Berjalan... Tekan Ctrl+C untuk berhenti.")

    # --- PENGATURAN JADWAL ---
    # 1. MODE TESTING (Setiap 30 detik kirim reminder) -> PAKAI INI DULU
    job_queue.run_repeating(kirim_reminder_grup, interval=60, first=10)

    # 2. MODE PRODUKSI (Setiap Hari jam 09.00 WIB) -> Nanti aktifkan ini
    # time_wib = datetime.time(hour=2, minute=0) # 02:00 UTC = 09:00 WIB
    # job_queue.run_daily(kirim_reminder_grup, time=time_wib, days=(0, 1, 2, 3, 4)) 

    app.run_polling()