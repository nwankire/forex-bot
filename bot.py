import os
import logging
import requests
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

TOKEN = os.environ.get('TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Binary options pairs - Pocket Option favorites
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY"]
TIMEFRAMES = ["M1", "M5"] # Pocket Option timeframes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 Binary Signal Bot Active\n\n"
        "⚡ Auto signals every 4 minutes\n"
        "Commands:\n"
        "/price EURUSD - Get live price\n"
        "/signal - Force signal now\n"
        "/id - Get your chat ID\n"
        "/stop - Pause auto signals\n"
        "/start_signals - Resume auto signals"
    )

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Chat ID: `{update.effective_chat.id}`", parse_mode='Markdown')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price EURUSD")
        return
    symbol = context.args[0].upper()
    try:
        response = requests.get(f"https://api.twelvedata.com/price?symbol={symbol}&apikey=demo", timeout=5)
        data = response.json()
        if "price" in data:
            await update.message.reply_text(f"💰 {symbol}: {data['price']}")
        else:
            await update.message.reply_text(f"❌ Couldn't find {symbol}")
    except:
        await update.message.reply_text("⚠️ Error fetching price")

async def send_binary_signal(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 4 minutes automatically"""
    if not CHAT_ID:
        return
        
    pair = random.choice(PAIRS)
    direction = random.choice(["CALL", "PUT"]) # CALL = Buy, PUT = Sell for binary
    timeframe = random.choice(TIMEFRAMES)
    
    # Optional: Get current price so entry is real
    try:
        res = requests.get(f"https://api.twelvedata.com/price?symbol={pair}&apikey=demo", timeout=3)
        price = res.json().get("price", "N/A")
    except:
        price = "N/A"
    
    text = f"""
⚡ **BINARY SIGNAL** ⚡

**PAIR:** {pair}
**ACTION:** {direction} {'🟢' if direction == 'CALL' else '🔴'}
**TIMEFRAME:** {timeframe}
**ENTRY:** {price}
**EXPIRY:** {timeframe}

*Trade responsibly. 1-3% per trade.*
"""
    await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')

async def force_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_binary_signal(context)

async def stop_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_jobs = context.job_queue.get_jobs_by_name("binary_signal")
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 Auto signals paused. Use /start_signals to resume")

async def start_signals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.job_queue.run_repeating(send_binary_signal, interval=240, first=5, name="binary_signal") # 240 sec = 4 mins
    await update.message.reply_text("✅ Auto signals started. Every 4 minutes.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", force_signal))
    app.add_handler(CommandHandler("stop", stop_signals))
    app.add_handler(CommandHandler("start_signals", start_signals))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # Start auto signals immediately on boot
    if CHAT_ID:
        app.job_queue.run_repeating(send_binary_signal, interval=240, first=10, name="binary_signal") # 4 mins
    
    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    
    print("Starting webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
