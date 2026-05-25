import os
import telebot
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Get tokens from Render Environment Variables
TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = int(os.environ.get('CHAT_ID'))

# Safety check
if not TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN or CHAT_ID not set in Environment Variables!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# Bot state
bot_running = False
active_pair = "EURUSD"

def send_signals():
    """Background thread that sends signals every 5 min"""
    global bot_running
    while bot_running:
        try:
            price = 1.0850 # Replace with real price later
            signal = f"🔥 {active_pair} SIGNAL\n\nBUY @ {price}\nTP: {price + 0.0020}\nSL: {price - 0.0010}\n\nTime: {time.strftime('%H:%M:%S')}"
            bot.send_message(CHAT_ID, signal)
            time.sleep(300) # 5 minutes
        except Exception as e:
            print(f"Error sending signal: {e}")
            time.sleep(60)

@bot.message_handler(commands=['startbot'])
def start_bot(message):
    global bot_running
    if bot_running:
        bot.reply_to(message, '⚠️ Bot already running')
        return
    bot_running = True
    threading.Thread(target=send_signals, daemon=True).start()
    bot.reply_to(message, f'✅ Auto signals STARTED\nPair: {active_pair}\nSignals every 5 min')

@bot.message_handler(commands=['stopbot'])
def stop_bot(message):
    global bot_running
    bot_running = False
    bot.reply_to(message, '🛑 Auto signals STOPPED')

@bot.message_handler(commands=['status'])
def status(message):
    status = "Running ✅" if bot_running else "Stopped 🛑"
    bot.reply_to(message, f'📊 Status: {status}\nPair: {active_pair}')

@bot.message_handler(commands=['setpair'])
def set_pair(message):
    global active_pair
    try:
        new_pair = message.text.split()[1].upper()
        active_pair = new_pair
        bot.reply_to(message, f'✅ Pair changed to {active_pair}')
    except:
        bot.reply_to(message, '❌ Usage: /setpair EURUSD')

# DUMMY WEB SERVER FOR RENDER FREE TIER
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is alive')
    
    def log_message(self, format, *args):
        pass # Don't spam logs

def run_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Health server running on port {port}")
    server.serve_forever()

# MAIN EXECUTION
if __name__ == "__main__":
    print("Bot starting...")
    
    # Start dummy web server in background so Render doesn't kill us
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # KILL ALL GHOST INSTANCES - This fixes 409 conflicts
    bot.remove_webhook()
    time.sleep(1)
    
    # Start polling - skip_pending=True kills other connections
    print("Starting polling...")
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
