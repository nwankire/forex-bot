import os
import telebot
from telebot import types
import threading
import time

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

@bot.message_handler(commands=['setpair'])
def set_pair(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("EURUSD", callback_data="pair_EURUSD"),
        types.InlineKeyboardButton("GBPUSD", callback_data="pair_GBPUSD")
    )
    markup.add(
        types.InlineKeyboardButton("XAUUSD", callback_data="pair_XAUUSD"),
        types.InlineKeyboardButton("USDJPY", callback_data="pair_USDJPY")
    )
    bot.send_message(message.chat.id, 'Pick a pair:', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pair_'))
def handle_pair(call):
    global active_pair
    active_pair = call.data.split("_")[1]
    bot.edit_message_text(f'✅ Active pair set to: {active_pair}', 
                         call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['status'])
def status(message):
    status = "Running ✅" if bot_running else "Stopped 🛑"
    bot.reply_to(message, f'Status: {status}\nPair: {active_pair}')

print("Bot starting...")
bot.infinity_polling()
