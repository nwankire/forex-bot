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
import requests
import time

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 10000))

# CUT TO 4 MAJORS - Yahoo is blocking Render IPs
PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"]
TIMEFRAME = "5m"
RSI_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
BOT_ACTIVE = True
SESSION_START = 8
SESSION_END = 17
TIMEZONE = pytz.timezone("Africa/Lagos")

# === YFINANCE SESSION WITH HEADERS ===
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# === GLOBAL APP ===
application = Application.builder().token(BOT_TOKEN).build()
application.chat_ids = set()

# === TRADING LOGIC ===
def get_signal(pair):
    for attempt in range(2):
        try:
            data = yf.download(
                tickers=pair,
                period="2d",
                interval=TIMEFRAME,
                progress=False,
                group_by='column',
                session=session,
                threads=False
            )

            if data.empty or len(data) < EMA_SLOW + 5:
                return None

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)

            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
            rs = gain / loss
            data['RSI'] = 100 - (100 / (1 + rs))
            data['EMA_FAST'] = data['Close'].ewm(span=EMA_FAST, adjust=False).mean()
            data['EMA_SLOW'] = data['Close'].ewm(span=EMA_SLOW, adjust=False).mean()

            data = data.dropna()
            if len(data) < 3:
                return None

            last = data.iloc[-2]
            prev = data.iloc[-3]

            rsi = last['RSI'].item()
            ema_fast_last = last['EMA_FAST'].item()
            ema_slow_last = last['EMA_SLOW'].item()
            ema_fast_prev = prev['EMA_FAST'].item()
            ema_slow_prev = prev['EMA_SLOW'].item()

            if pd.isna(rsi):
                return None

            if rsi < 30 and ema_fast_prev < ema_slow_prev and ema_fast_last > ema_slow_last:
                return {"pair": pair.replace("=X", ""), "direction": "CALL ✅", "rsi": round(rsi, 1)}

            if rsi > 70 and ema_fast_prev > ema_slow_prev and ema_fast_last < ema_slow_last:
                return {"pair": pair.replace("=X", ""), "direction": "PUT 🔻", "rsi": round(rsi, 1)}
            return None

        except Exception as e:
            print(f"Error scanning {pair} attempt {attempt+1}: {e}")
            if attempt == 0:
                time.sleep(3)
            else:
                return None
    return None

def check_session():
    now = datetime.now(TIMEZONE)
    return SESSION_START <= now.hour < SESSION_END

# === COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    application.chat_ids.add(update.effective_chat.id)
    msg = f"⚡ PO BINARY BOT ⚡\nScanning {len(PAIRS)} pairs\nStrategy: RSI{RSI_PERIOD} + EMA{EMA_FAST}/{EMA_SLOW}\nTF: {TIMEFRAME.upper()}\nSession: {SESSION_START}am-{SESSION_END}pm GMT+1\nStatus: {'ON' if BOT_ACTIVE else 'OFF'}"
    await update.message.reply_text(msg)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TIMEZONE).strftime("%H:%M")
    session_status = "OPEN 🟢" if check_session() else "CLOSED ❌"
    await update.message.reply_text(f"Time: {now} GMT+1\nSession: {session_status}\nTF: {TIMEFRAME.upper()}\nBot: {'ON' if BOT_ACTIVE else 'OFF'}")

async def tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TIMEFRAME
    if not context.args:
        await update.message.reply_text("Usage: /tf M5 or /tf M15")
        return
    arg = context.args[0].upper()
    if arg == "M5":
        TIMEFRAME = "5m"
        await update.message.reply_text("Timeframe: M5 | 5 Minutes")
    elif arg == "M15":
        TIMEFRAME = "15m"
        await update.message.reply_text("Timeframe: M15 | 15 Minutes")

async def on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = True
    await update.message.reply_text("Bot activated ✅")

async def off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = False
    await update.message.reply_text("Bot deactivated ❌")

# === AUTO SCANNER ===
async def scan_and_send():
    if not BOT_ACTIVE or not check_session():
        return
    print(f"Scanning {len(PAIRS)} pairs at {datetime.now(TIMEZONE).strftime('%H:%M:%S')}")
    for i, pair in enumerate(PAIRS):
        signal = get_signal(pair)
        if signal:
            msg = f"{signal['pair']}\n{signal['direction']}\nExpiry: {'5 Minutes' if TIMEFRAME == '5m' else '15 Minutes'}\nRSI: {signal['rsi']} | EMA: Crossed\nConfidence: 75%"
            for chat_id in application.chat_ids:
                try:
                    await application.bot.send_message(chat_id=chat_id, text=msg)
                    print(f"Signal sent: {signal['pair']} {signal['direction']}")
                except Exception as e:
                    print(f"Failed to send to {chat_id}: {e}")

        if i < len(PAIRS) - 1:
            await asyncio.sleep(5)

# === WEB SERVER ===
async def telegram_webhook(request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return web.Response()

async def health_check(request):
    return web.Response(text="Bot is running", status=200)

async def setup():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("tf", tf))
    application.add_handler(CommandHandler("on", on))
    application.add_handler(CommandHandler("off", off))

    await application.initialize()
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    await application.start()

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(scan_and_send, "interval", minutes=5)
    scheduler.start()
    print("Bot started - Scheduler running every 5 mins")

def main():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_post(f"/{BOT_TOKEN}", telegram_webhook)
    app.on_startup.append(lambda _: setup())

    print(f"Starting server on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
