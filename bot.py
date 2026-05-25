import os
import logging
import requests
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get('TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
API_KEY = "demo"

# ALL MAJOR + POPULAR CROSSES FOR POCKET OPTION
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY",
    "EURGBP", "EURAUD"
]

TIMEZONE = pytz.timezone("Africa/Lagos") # GMT+1

SETTINGS = {
    "timeframe": "M1",
    "interval": 60,
    "rsi_buy_zone": [30, 50],
    "rsi_sell_zone": [50, 70],
    "active": True
}

TF_CONFIG = {
    "M1": {"interval": 60, "expiry": "1 Minute", "rsi_buy": [30, 50], "rsi_sell": [50, 70]},
    "M5": {"interval": 240, "expiry": "5 Minutes", "rsi_buy": [40, 60], "rsi_sell": [40, 60]},
    "M15": {"interval": 900, "expiry": "15 Minutes", "rsi_buy": [45, 55], "rsi_sell": [45, 55]}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚡ **PO BINARY BOT** ⚡\n\n"
        f"Scanning {len(PAIRS)} pairs\n"
        f"Strategy: RSI14 + EMA9/21\n"
        f"Current TF: {SETTINGS['timeframe']} | {TF_CONFIG[SETTINGS['timeframe']]['expiry']}\n"
        f"Session: 8am-5pm GMT+1\n"
        f"Status: {'ON' if SETTINGS['active'] else 'OFF'}\n\n"
        f"Commands:\n"
        f"/tf M1 | M5 | M15 - Change timeframe\n"
        f"/signal - Force scan all pairs now\n"
        f"/pairs - List all pairs\n"
        f"/on - Resume auto signals\n"
        f"/off - Pause auto signals\n"
        f"/status - Check session + TF"
    )

async def change_tf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].upper() not in TF_CONFIG:
        await update.message.reply_text("Usage: /tf M1 or /tf M5 or /tf M15")
        return

    tf = context.args[0].upper()
    SETTINGS["timeframe"] = tf
    SETTINGS["interval"] = TF_CONFIG[tf]["interval"]
    SETTINGS["rsi_buy_zone"] = TF_CONFIG[tf]["rsi_buy"]
    SETTINGS["rsi_sell_zone"] = TF_CONFIG[tf]["rsi_sell"]

    current_jobs = context.job_queue.get_jobs_by_name("binary_signal")
    for job in current_jobs:
        job.schedule_removal()
    if SETTINGS["active"]:
        context.job_queue.run_repeating(send_binary_signal, interval=SETTINGS["interval"], first=5, name="binary_signal")

    await update.message.reply_text(
        f"✅ Timeframe: {tf}\n"
        f"Expiry: {TF_CONFIG[tf]['expiry']}\n"
        f"Scan interval: {SETTINGS['interval']//60} mins\n"
        f"Scanning {len(PAIRS)} pairs"
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
    return now.weekday() < 5 and 8 <= now.hour < 17

async def fetch_candles(symbol, interval):
    try:
        tf_api = "1min" if interval == "M1" else "5min" if interval == "M5" else "15min"
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={tf_api}&outputsize=50&apikey={API_KEY}"
        res = requests.get(url, timeout=10).json()
        if "values" not in res: return None
        candles = res["values"][::-1]
        closes = [float(c["close"]) for c in candles]
        return closes, candles
    except:
        return None

async def analyze_pair(symbol):
    data = await fetch_candles(symbol, SETTINGS["timeframe"])
    if not data: return None
    closes, candles = data

    ema9 = get_ema(closes, 9)
    ema21 = get_ema(closes, 21)
    rsi = get_rsi(closes, 14)
    if not all([ema9, ema21, rsi]): return None

    last_close = closes[-1]
    prev_close = closes[-2]
    last_candle_green = last_close > prev_close

    if ema9 > ema21 and SETTINGS["rsi_buy_zone"][0] < rsi < SETTINGS["rsi_buy_zone"][1] and last_candle_green:
        return {"pair": symbol, "action": "CALL", "rsi": f"{rsi:.1f}", "price": last_close}

    if ema9 < ema21 and SETTINGS["rsi_sell_zone"][0] < rsi < SETTINGS["rsi_sell_zone"][1] and not last_candle_green:
        return {"pair": symbol, "action": "PUT", "rsi": f"{rsi:.1f}", "price": last_close}
    return None

async def send_binary_signal(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID or not SETTINGS["active"] or not is_trading_session(): return

    signals_found = []
    for pair in PAIRS:
        signal = await analyze_pair(pair)
        if signal:
            signals_found.append(signal)

    for signal in signals_found:
        text = f"""
⚡ **{signal['action']}** ⚡

**PAIR:** {signal['pair']} {'🟢' if signal['action'] == 'CALL' else '🔴'}
**TIMEFRAME:** {SETTINGS['timeframe']} | **EXPIRY:** {TF_CONFIG[SETTINGS['timeframe']]['expiry']}
**ENTRY:** {signal['price']:.5f}
**RSI:** {signal['rsi']} | **EMA9/21 Cross**

_Pick your setup. 1% risk max._
"""
        await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')

async def force_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔍 Scanning {len(PAIRS)} pairs on {SETTINGS['timeframe']}...")
    await send_binary_signal(context)

async def toggle_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS["active"] = True
    context.job_queue.run_repeating(send_binary_signal, interval=SETTINGS["interval"], first=5, name="binary_signal")
    await update.message.reply_text("✅ Auto signals ON")

async def toggle_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS["active"] = False
    current_jobs = context.job_queue.get_jobs_by_name("binary_signal")
    for job in current_jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 Auto signals OFF")

async def show_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs_text = "\n".join([f"• {p}" for p in PAIRS])
    await update.message.reply_text(f"**Scanning {len(PAIRS)} pairs:**\n{pairs_text}", parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = "ACTIVE ✅" if is_trading_session() else "CLOSED ❌"
    now = datetime.now(TIMEZONE).strftime("%H:%M")
    await update.message.reply_text(
        f"**Status**\n"
        f"Time: {now} GMT+1\n"
        f"Session: {session}\n"
        f"TF: {SETTINGS['timeframe']} | {TF_CONFIG[SETTINGS['timeframe']]['expiry']}\n"
        f"Bot: {'ON' if SETTINGS['active'] else 'OFF'}\n"
        f"Pairs: {len(PAIRS)}", parse_mode='Markdown'
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tf", change_tf))
    app.add_handler(CommandHandler("signal", force_signal))
    app.add_handler(CommandHandler("pairs", show_pairs))
    app.add_handler(CommandHandler("on", toggle_on))
    app.add_handler(CommandHandler("off", toggle_off))
    app.add_handler(CommandHandler("status", status))

    if CHAT_ID and SETTINGS["active"]:
        app.job_queue.run_repeating(send_binary_signal, interval=SETTINGS["interval"], first=10, name="binary_signal")

    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")

if __name__ == '__main__':
    main()
