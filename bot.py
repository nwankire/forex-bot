import os
import logging
import requests
import pytz
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiohttp import web

# ============ CONFIG ============
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_KEY = os.environ.get('API_KEY', 'demo')
CHAT_ID = os.environ.get('CHAT_ID')

PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "NZD/USD",
    "USD/CHF", "EUR/AUD", "GBP/AUD", "EUR/CAD"
]

TIMEFRAME = "5min"
EXPIRY = "5 Minutes"
SCAN_INTERVAL = 4
BOT_ACTIVE = True
TZ = pytz.timezone('Africa/Lagos')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ HEALTH CHECK FOR UPTIMEROBOT ============
async def health(_):
    return web.Response(text="OK")

# ============ TRADING LOGIC ============
def get_data(pair, interval="5min"):
    try:
        symbol = pair.replace("/", "")
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": 30,
            "apikey": API_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "values" not in data:
            logger.error(f"No data for {pair}: {data}")
            return None
        closes = [float(x["close"]) for x in data["values"][::-1]]
        return {"close": closes}
    except Exception as e:
        logger.error(f"Error fetching {pair}: {e}")
        return None

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = values[i] - values[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            losses.append(abs(change))
            gains.append(0)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def check_signal(pair):
    data = get_data(pair, TIMEFRAME)
    if not data or len(data["close"]) < 21:
        return None
    closes = data["close"]
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    rsi14 = rsi(closes, 14)
    if not ema9 or not ema21 or not rsi14:
        return None
    prev_ema9 = ema(closes[:-1], 9)
    prev_ema21 = ema(closes[:-1], 21)
    signal = None
    entry = closes[-1]
    if prev_ema9 <= prev_ema21 and ema9 > ema21 and 40 < rsi14 < 60 and closes[-1] > closes[-2]:
        signal = "CALL"
    elif prev_ema9 >= prev_ema21 and ema9 < ema21 and 40 < rsi14 < 60 and closes[-1] < closes[-2]:
        signal = "PUT"
    if signal:
        return {
            "pair": pair,
            "signal": signal,
            "entry": entry,
            "rsi": round(rsi14, 1)
        }
    return None

def is_session_active():
    now = datetime.now(TZ)
    hour = now.hour
    return 8 <= hour < 17

async def scan_and_send(context: ContextTypes.DEFAULT_TYPE):
    if not BOT_ACTIVE or not is_session_active():
        return
    for pair in PAIRS:
        result = check_signal(pair)
        if result:
            emoji = "🟢" if result["signal"] == "CALL" else "🔴"
            msg = f"""⚡ {result["signal"]} ⚡

PAIR: {result["pair"]} {emoji}
TIMEFRAME: {TIMEFRAME.replace('min','M')} | EXPIRY: {EXPIRY}
ENTRY: {result["entry"]}
RSI: {result["rsi"]} | EMA9/21 Cross

_Pick your setup. 1% risk max._"""
            await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
            logger.info(f"Signal sent: {result['pair']} {result['signal']}")

# ============ TELEGRAM COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    await update.message.reply_text(
        f"""⚡ PO BINARY BOT ⚡

Scanning {len(PAIRS)} pairs
Strategy: RSI14 + EMA9/21
Current TF: {TIMEFRAME.replace('min','M')} | {EXPIRY}
Session: 8am-5pm GMT+1
Status: {"ON" if BOT_ACTIVE else "OFF"}

Commands:
/on - Start auto signals
/off - Stop auto signals
/status - Check bot status
/signal - Force scan now
/tf M1|M5|M15 - Change timeframe"""
    )

async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = True
    await update.message.reply_text("✅ Auto signals ON")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ACTIVE
    BOT_ACTIVE = False
    await update.message.reply_text("❌ Auto signals OFF")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    session = "ACTIVE ✅" if is_session_active() else "CLOSED ❌"
    await update.message.reply_text(
        f"""Status
Time: {now.strftime('%H:%M')} GMT+1
Session: {session}
TF: {TIMEFRAME.replace('min','M')} | {EXPIRY}
Bot: {"ON" if BOT_ACTIVE else "OFF"}
Pairs: {len(PAIRS)}"""
    )

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Scanning {len(PAIRS)} pairs on {TIMEFRAME.replace('min','M')}...")
    await scan_and_send(context)

async def tf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TIMEFRAME, EXPIRY, SCAN_INTERVAL
    if not context.args:
        await update.message.reply_text("Usage: /tf M1|M5|M15")
        return
    tf = context.args[0].upper()
    if tf == "M1":
        TIMEFRAME, EXPIRY, SCAN_INTERVAL = "1min", "1 Minute", 1
    elif tf == "M5":
        TIMEFRAME, EXPIRY, SCAN_INTERVAL = "5min", "5 Minutes", 4
    elif tf == "M15":
        TIMEFRAME, EXPIRY, SCAN_INTERVAL = "15min", "15 Minutes", 15
    else:
        await update.message.reply_text("Invalid. Use: M1, M5, or M15")
        return
    for job in context.job_queue.jobs():
        job.schedule_removal()
    context.job_queue.run_repeating(scan_and_send, interval=SCAN_INTERVAL*60, first=10)
    await update.message.reply_text(
        f"""✅ Timeframe: {tf}
Expiry: {EXPIRY}
Scan interval: {SCAN_INTERVAL} mins
Scanning {len(PAIRS)} pairs"""
    )

# ============ MAIN ============
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Add health check route for UptimeRobot GET requests
    async def post_init(app):
        app.web_app.router.add_get("/", health)

    application.post_init = post_init

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("on", on_command))
    application.add_handler(CommandHandler("off", off_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("signal", signal_command))
    application.add_handler(CommandHandler("tf", tf_command))

    application.job_queue.run_repeating(scan_and_send, interval=SCAN_INTERVAL*60, first=10)

    PORT = int(os.environ.get('PORT', 10000))
    WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')

    logger.info(f"Starting webhook on port {PORT}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/",
        url_path=""
    )

if __name__ == "__main__":
    main()
