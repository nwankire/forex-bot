import os
import telebot
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = int(os.environ.get('CHAT_ID'))
bot = telebot.TeleBot(TOKEN)

bot_running = False
active_pair = "EURUSD"

def send_signals():
    global bot_running
    while bot_running:
        price = 1.0850
        signal = f"🔥 {active_pair} SIGNAL\nBUY @ {price}\nTP: {price + 0.0020}\nSL: {price - 0.0010}"
        bot.send_message(CHAT_ID, signal)
        time.sleep(300)

@bot.message_handler(commands=['startbot'])
def start_bot(message):
    global bot_running
    if bot_running:
        bot.reply_to(message, 'Bot already running')
        return
    bot_running = True
    threading.Thread(target=send_signals, daemon=True).start()
    bot.reply_to(message, f'✅ Auto signals started\nPair: {active_pair}')

@bot.message_handler(commands=['stopbot'])
def stop_bot(message):
    global bot_running
    bot_running = False
    bot.reply_to(message, '🛑 Auto signals stopped')

@bot.message_handler(commands=['status'])
def status(message):
    status = "Running ✅" if bot_running else "Stopped 🛑"
    bot.reply_to(message, f'Status: {status}\nPair: {active_pair}')

# DUMMY WEB SERVER - Makes Render free tier happy
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot running')

def run_server():
    port = int(os.environ.get('PORT', 10000))
    HTTPServer(('0.0.0.0', port), HealthHandler).serve_forever()

print("Bot starting...")
threading.Thread(target=run_server, daemon=True).start()
bot.infinity_polling()
