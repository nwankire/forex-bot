import os
import logging
import requests
from datetime import time, datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get('TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = "demo" # TwelveData free key

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY"]
TIMEZONE = pytz.timezone("Africa/Lagos") # GMT+1 for Port Harcourt

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **PO BINARY BOT ACTIVE** ⚡\n\n"
        "Strategy: RSI14 + EMA9/21 Cross\n"
        "Timeframe: M1\n"
        "Session: 8am-5pm GMT+1 only\n\n"
        "Commands:\n"
        "/signal - Force signal now\n"
        "/status - Check if market session active"
    )

def get_ema(values, period):
    if len(values) < period: return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for price in values[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def get_rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def is_trading_session():
    now = datetime.now(TIMEZONE)
    # Monday-Friday, 8am-5pm GMT+1
    return now.weekday() < 5 and 8 <= now.hour < 17

async def fetch_candles(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=50&apikey={API_KEY}"
        res = requests.get(url, timeout=10).json()
        if "values" not in res: return None
        candles = res["values"][::-1] # Oldest first
        closes = [float(c["close"]) for c in candles]
        return closes, candles
    except:
        return None

async def analyze_pair(symbol):
    data = await fetch_candles(symbol)
    if not data: return None
    closes, candles = data

    ema9 = get_ema(closes, 9)
    ema21 = get_ema(closes, 21)
    rsi = get_rsi(closes, 14)

    if not all([ema9, ema21, rsi]): return None

    last_close = closes[-1]
    prev_close = closes[-2]
    last_candle_green = last_close > prev_close

    # CALL setup
    if ema9 > ema21 and 30 < rsi < 50 and last_candle_green:
        return {"pair": symbol, "action": "CALL", "rsi": f"{rsi:.1f}", "price": last_close}

    # PUT setup
    if ema9 < ema21 and 50 < rsi < 70 and not last_candle_green:
        return {"pair": symbol, "action": "PUT", "rsi": f"{rsi:.1f}", "price": last_close}

    return None

async def send_binary_signal(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID: return
    if not is_trading_session(): return # Skip outside 8am-5pm

    for pair in PAIRS:
        signal = await analyze_pair(pair)
        if signal:
            text = f"""
⚡ **LIVE SIGNAL** ⚡

**PAIR:** {signal['pair']}
**ACTION:** {signal['action']} {'🟢' if signal['action'] == 'CALL' else '🔴'}
**TIMEFRAME:** M1
**EXPIRY:** 1 Minute
**ENTRY:** {signal['price']:.5f}

**SETUP:** EMA9/21 Cross + RSI {signal['rsi']}
**SESSION:** London/NY Active

_Risk 1% max. Demo test 20 trades first._
"""
            await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')
            return # Send only 1 signal per cycle to avoid spam

async def force_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning market...")
    await send_binary_signal(context)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = "ACTIVE ✅" if is_trading_session() else "CLOSED ❌"
    now = datetime.now(TIMEZONE).strftime("%H:%M")
    await update.message.reply_text(f"Time: {now} GMT+1\nTrading Session: {session}\nPairs: {', '.join(PAIRS)}")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", force_signal))
    app.add_handler(CommandHandler("status", status))

    # Check market every 60 seconds, but only sends if setup forms + session active
    if CHAT_ID:
        app.job_queue.run_repeating(send_binary_signal, interval=60, first=10)

    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
