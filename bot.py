import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = int(os.environ.get('CHAT_ID'))

bot_running = False
active_pair = "EURUSD"
signal_task = None

async def check_and_send_signal():
    global bot_running
    while bot_running:
        price = 1.0850
        signal = f"🔥 {active_pair} SIGNAL\nBUY @ {price}\nTP: {price + 0.0020}\nSL: {price - 0.0010}"
        await app.bot.send_message(chat_id=CHAT_ID, text=signal)
        await asyncio.sleep(300)

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running, signal_task
    if bot_running:
        await update.message.reply_text('Bot already running')
        return
    bot_running = True
    signal_task = asyncio.create_task(check_and_send_signal())
    await update.message.reply_text(f'✅ Auto signals started\nPair: {active_pair}')

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running, signal_task
    bot_running = False
    if signal_task:
        signal_task.cancel()
    await update.message.reply_text('🛑 Auto signals stopped')

async def set_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("EURUSD", callback_data="pair_EURUSD"),
         InlineKeyboardButton("GBPUSD", callback_data="pair_GBPUSD")],
        [InlineKeyboardButton("XAUUSD", callback_data="pair_XAUUSD"),
         InlineKeyboardButton("USDJPY", callback_data="pair_USDJPY")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Pick a pair:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_pair
    query = update.callback_query
    await query.answer()
    if query.data.startswith("pair_"):
        active_pair = query.data.split("_")[1]
        await query.edit_message_text(f'✅ Active pair set to: {active_pair}')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "Running ✅" if bot_running else "Stopped 🛑"
    await update.message.reply_text(f'Status: {status}\nPair: {active_pair}')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("startbot", start_bot))
    app.add_handler(CommandHandler("stopbot", stop_bot))
    app.add_handler(CommandHandler("setpair", set_pair))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(button_handler))

    # THIS IS ALL YOU NEED - NO WEBHOOK, NO FLASK, NO GUNICORN
    print("Bot starting in polling mode...")
    app.run_polling()
