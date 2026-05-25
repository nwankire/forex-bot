import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get('TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Bot settings - you can change these live
USER_SETTINGS = {
    "timeframe": "M1", # Default M1. Use /tf M5 to change
    "pairs": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
    "active": True
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚡ Binary Bot Online\n\n"
        f"Current TF: {USER_SETTINGS['timeframe']}\n"
        f"Auto signal: {'ON' if USER_SETTINGS['active'] else 'OFF'}\n\n"
        f"Commands:\n"
        f"/tf M1 - Switch to 1 min\n"
        f"/tf M5 - Switch to 5 min\n"
        f"/signal - Force signal now\n"
        f"/stop - Pause bot\n"
        f"/start_bot - Resume bot\n"
        f"/pairs - See active pairs"
    )

async def change_tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"Current timeframe: {USER_SETTINGS['timeframe']}\nUsage: /tf M1 or /tf M5")
        return
    
    tf = context.args[0].upper()
    if tf in ["M1", "M5", "M15"]:
        USER_SETTINGS["timeframe"] = tf
        # Update job interval based on timeframe
        interval = 60 if tf == "M1" else 240 if tf == "M5" else 900
        current_jobs = context.job_queue.get_jobs_by_name("binary_signal")
        for job in current_jobs:
            job.schedule_removal()
        context.job_queue.run_repeating(send_binary_signal, interval=interval, first=5, name="binary_signal")
        await update.message.reply_text(f"✅ Timeframe changed to {tf}\nNew signal interval: {interval//60} mins")
    else:
        await update.message.reply_text("❌ Use M1, M5, or M15")

async def send_binary_signal(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID or not USER_SETTINGS["active"]:
        return
    
    tf = USER_SETTINGS["timeframe"]
    pair = random.choice(USER_SETTINGS["pairs"])
    
    # THIS IS WHERE YOU ADD REAL STRATEGY LATER
    # Right now it's still random. Replace this section with RSI/EMA logic
    direction = random.choice(["CALL", "PUT"])
    reason = "Test signal - add RSI/EMA logic here"
    
    # Get live price for entry
    try:
        res = requests.get(f"https://api.twelvedata.com/price?symbol={pair}&apikey=demo", timeout=3)
        price = res.json().get("price", "N/A")
    except:
        price = "N/A"
    
    text = f"""
⚡ **POCKET OPTION SIGNAL** ⚡

**PAIR:** {pair}
**ACTION:** {direction} {'🟢' if direction == 'CALL' else '🔴'}
**TIMEFRAME:** {tf}
**EXPIRY:** {tf}
**ENTRY:** {price}

**REASON:** {reason}

_Risk 1% max. Demo test first._
"""
    await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')

async def force_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_binary_signal(context)

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_SETTINGS["active"] = False
    await update.message.reply_text("🛑 Bot paused. Use /start_bot to resume")

async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_SETTINGS["active"] = True
    await update.message.reply_text("✅ Bot resumed")

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Active pairs: {', '.join(USER_SETTINGS['pairs'])}")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tf", change_tf))
    app.add_handler(CommandHandler("signal", force_signal))
    app.add_handler(CommandHandler("stop", stop_bot))
    app.add_handler(CommandHandler("start_bot", start_bot))
    app.add_handler(CommandHandler("pairs", show_pairs))
    
    if CHAT_ID:
        # Start with M1 = 60 sec intervals
        app.job_queue.run_repeating(send_binary_signal, interval=60, first=10, name="binary_signal")
    
    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
