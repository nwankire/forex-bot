import os
import asyncio
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # https://forex-bot-1-1df7.onrender.com
PORT = int(os.environ.get("PORT", 10000))

# Trading config
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCHF=X", "USDCAD=X",
         "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURCHF=X",
         "GBPCHF=X", "CADJPY=X"]
TIMEFRAME = "5m" # Use /tf M15 to change
RSI_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
BOT_ACTIVE = True
SESSION_START = 8 # 8 AM
SESSION_END = 17 # 5 PM
TIMEZONE = pytz.timezone("Africa/Lagos") # GMT+1

# === TRADING LOGIC ===
def get_signal(pair):
    try:
        data = yf.download(tickers=pair, period="2d", interval=TIMEFRAME, progress=False)
        if len(data) < EMA_SLOW + 5:
            return None

        # Calculate RSI
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # Calculate EMAs
        data['EMA_FAST'] = data['Close'].ewm(span=EMA_FAST, adjust=False).mean()
        data['EMA_SLOW'] = data['Close'].ewm(span=EMA_SLOW, adjust=False).mean()

        last = data.iloc[-2] # Use closed candle
        prev = data.iloc[-3]

        rsi = last['RSI']
        ema_fast = last['EMA_FAST']
        ema_slow = last['EMA_SLOW']
        prev_ema_fast = prev['EMA_FAST']
        prev_ema_slow = prev['EMA_SLOW']

        # CALL signal: RSI < 30 + EMA cross up
        if rsi < 30 and prev_ema_fast < prev_ema_slow and ema_fast > ema_slow:
            return {"pair": pair.replace("=X", ""), "direction": "CALL ✅", "rsi": round(rsi, 1)}

        # PUT signal: RSI > 70 + EMA cross down
        if rsi > 70 and prev_ema_fast > prev_ema_slow and ema_fast < ema_slow:
            return {"pair": pair.replace("=X", ""), "direction": "PUT 🔻", "rsi": round(rsi, 1)}

        return None
    except Exception as e:
        print(f"Error scanning {pair}: {e}")
        return None

def check_session():
    now = datetime.now(TIMEZONE)
    return SESSION_START <= now.hour < SESSION_END

# === TELEGRAM COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""
⚡ PO BINARY BOT ⚡
Scanning {len(PAIRS)} pairs
Strategy: RSI{RSI_PERIOD} + EMA{EMA_FAST}/{EMA_SLOW}
Current TF: {TIMEFRAME.upper()} | {"5 Minutes" if TIMEFRAME == "5m" else "15 Minutes"}
Session: {SESSION_START}am-{SESSION_END}pm GMT+1
Status: {"ON" if BOT_ACTIVE else "OFF"}
"""
    await update.message.reply_text(msg)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE).strftime("%H:%M")
    session_status = "OPEN 🟢" if check_session() else "CLOSED ❌"
    msg = f"""
Status
Time: {now} GMT+1
Session: {session_status}
TF: {TIMEFRAME.upper()} | {"5 Minutes" if TIMEFRAME == "5m" else "15 Minutes"}
Bot: {"ON" if BOT_ACTIVE else "OFF"}
Pairs: {len(PAIRS)}
"""
    await update.message.reply_text(msg)

async def tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TIMEFRAME
    if not context.args:
        await update.message.reply_text("Usage: /tf M5 or /tf M15")
        return

    arg = context.args[0].upper()
    if arg == "M5":
        TIMEFRAME = "5m"
        await update.message.reply_text("Timeframe changed to M5 | 5 Minutes")
    elif arg == "M15":
        TIMEFRAME = "15m"
        await update.message.reply_text("Timeframe changed to M15 | 15 Minutes")
    else:
        await update.message.reply_text("Invalid. Use /tf M5 or /tf M15")

async def on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = True
    await update.message.reply_text("Bot activated ✅")

async def off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = False
    await update.message.reply_text("Bot deactivated ❌")

# === AUTO SCANNER ===
async def scan_and_send(app: Application):
    if not BOT_ACTIVE or not check_session():
        return

    for pair in PAIRS:
        signal = get_signal(pair)
        if signal:
            msg = f"""
{signal['pair']}
{signal['direction']}
Expiry: {"5 Minutes" if TIMEFRAME == "5m" else "15 Minutes"}
RSI: {signal['rsi']} | EMA: Crossed
Confidence: 75%
"""
            for chat_id in app.chat_ids:
                try:
                    await app.bot.send_message(chat_id=chat_id, text=msg)
                except Exception as e:
                    print(f"Send error: {e}")
        await asyncio.sleep(1) # Rate limit

# === HEALTH CHECK + SETUP ===
async def health_check(request):
    return web.Response(text="Bot is running", status=200)

async def post_init(app: Application):
    app.chat_ids = set()
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(scan_and_send, "interval", minutes=4, args=[app])
    scheduler.start()
    print("Scheduler started")

    # Add health check route here - this is the correct spot
    app.web_app.router.add_get("/", health_check)

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.chat_ids.add(update.effective_chat.id)

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("tf", tf))
    app.add_handler(CommandHandler("on", on))
    app.add_handler(CommandHandler("off", off))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("pairs", start))
    app.add_handler(CommandHandler("session", start))

    # Track all chats for broadcasting
    app.add_handler(CommandHandler("start", track_chats), group=1)

    print(f"Starting webhook on port {PORT}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
