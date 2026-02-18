from telegram import Update
from telegram.ext import CommandHandler, Application, ContextTypes
 
async def callback_alarm(context: ContextTypes.DEFAULT_TYPE):
    # Beep the person who called this alarm:
    await context.bot.send_message(chat_id=context.job.chat_id, text=f'BEEP {context.job.data}!')
 
 
async def callback_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    name = update.effective_chat.full_name
    await context.bot.send_message(chat_id=chat_id, text='Setting a timer for 1 minute!')
    # Set the alarm:
    context.job_queue.run_once(callback_alarm, 60, data=name, chat_id=chat_id)
 
application = Application.builder().token('TOKEN').build()
timer_handler = CommandHandler('timer', callback_timer)
application.add_handler(timer_handler)
application.run_polling()