import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

TOKEN = os.environ.get('TOKEN')

# Free API, no key needed. Supports forex + crypto
PRICE_API = "https://api.twelvedata.com/price"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! 👋 I'm alive on Render 24/7\n\n"
        "Commands:\n"
        "/price XAUUSD - Get Gold price\n"
        "/price EURUSD - Get Euro price\n"
        "/price BTCUSD - Get Bitcoin price\n\n"
        "Just send any message and I'll echo it back."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /price SYMBOL to get live price\n"
        "Examples: /price XAUUSD, /price EURUSD, /price BTCUSD"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /price XAUUSD")
        return
    
    symbol = context.args[0].upper()
    
    try:
        # TwelveData works for forex + crypto + stocks
        response = requests.get(f"{PRICE_API}?symbol={symbol}&apikey=demo", timeout=10)
        data = response.json()
        
        if "price" in data:
            price_val = float(data["price"])
            
            # Format decimals based on asset type
            if "JPY" in symbol:
                formatted = f"{price_val:.3f}" # JPY pairs use 3 decimals
            elif any(x in symbol for x in ["XAU", "XAG", "BTC", "ETH"]):
                formatted = f"{price_val:.2f}" # Gold/Crypto use 2 decimals 
            else:
                formatted = f"{price_val:.5f}" # Major forex uses 5 decimals
                
            await update.message.reply_text(f"💰 {symbol}: {formatted}")
        else:
            await update.message.reply_text(f"❌ Couldn't find {symbol}. Try XAUUSD, EURUSD, BTCUSD")
            
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("⚠️ Error fetching price. Try again in 10 seconds.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
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
