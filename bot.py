import os
import telebot
import threading
import time

TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = int(os.environ.get('CHAT_ID'))
bot = telebot.TeleBot(TOKEN)

bot_running = False

@bot.message_handler(commands=['status'])
def status(message):
    bot.reply_to(message, 'Bot is working ✅')

print("Bot starting...")
bot.infinity_polling()
