import os
import logging
import requests
import random
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

TOKEN = os.environ.get('TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') # Your Telegram user ID or channel ID
PRICE_API = "https://api.twelvedata.com/price"

# Sample signals to rotate. Replace with your logic later
SIGNALS = [
    {
        "pair": "XAUUSD",
        "action": "BUY",
        "entry": "2345.50",
        "sl": "2335.00", 
        "tp1": "2355.00",
        "tp2": "2365.00"
    },
    {
        "pair": "EURUSD", 
        "action": "SELL",
        "entry": "1.08500",
        "sl": "1.08800",
        "tp1": "1.08200", 
        "tp2": "1.07900"
    },
    {
        "pair": "GBPJPY",
        "action": "BUY", 
        "entry": "197.350",
        "sl": "196.800",
        "tp1": "198.000",
        "tp2": "198.500"
    }
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 I'm alive on Render 24/7\n\n"
        "Auto signals active ✅\n"
        "Commands:\n"
        "/price XAUUSD - Get live price\n"
        "/signal - Force send a signal now\n"
        "/id - Get your chat ID"
    )

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Chat ID: `{update.effective_chat.id}`", parse_mode='Markdown')

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price XAUUSD")
        return
    
    symbol = context.args[0].upper()
    try:
        response = requests.get(f"{PRICE_API}?symbol={symbol}&apikey=demo", timeout=10)
        data = response.json()
        if "price" in data:
            price_val = float(data["price"])
            if "JPY" in symbol:
                formatted = f"{price_val:.3f}"
            elif any(x in symbol for x in ["XAU", "XAG", "BTC", "ETH"]):
                formatted = f"{price_val:.2f}"
            else:
                formatted = f"{price_val:.5f}"
            await update.message.reply_text(f"💰 {symbol}: {formatted}")
        else:
            await update.message.reply_text(f"❌ Couldn't find {symbol}")
    except:
        await update.message.reply_text("⚠️ Error fetching price")

async def send_signal(context: ContextTypes.DEFAULT_TYPE):
    """This function runs automatically"""
    if not CHAT_ID:
        logging.error("CHAT_ID not set")
        return
        
    signal = random.choice(SIGNALS) # Pick random signal for now
    
    text = f"""
🔥 **AUTO SIGNAL** 🔥

📊 **Pair:** {signal['pair']}
📈 **Action:** {signal['action']}
💵 **Entry:** {signal['entry']}
🛑 **SL:** {signal['sl']}
🎯 **TP1:** {signal['tp1']}
🎯 **TP2:** {signal['tp2']}

_Risk 1% per trade. Not financial advice._
"""
    await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')

async def force_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual /signal command"""
    await send_signal(context)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", force_signal))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # AUTO SIGNAL SCHEDULER
    if CHAT_ID:
        job_queue = app.job_queue
        # Run every 4 hours. Change to seconds=60 for testing
        job_queue.run_repeating(send_signal, interval=14400, first=10) 
        # Run at specific times: 9am, 1pm, 5pm GMT+1
        job_queue.run_daily(send_signal, time=time(hour=8, minute=0)) # 9am GMT+1
        job_queue.run_daily(send_signal, time=time(hour=12, minute=0)) # 1pm GMT+1
        job_queue.run_daily(send_signal, time=time(hour=16, minute=0)) # 5pm GMT+1
    
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
