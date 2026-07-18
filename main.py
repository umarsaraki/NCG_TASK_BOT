import telebot
import os
from supabase import create_client, Client

# Saka token din ka a Secrets/Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Sannu da zuwa! Bot din yana aiki ✅")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f'Ka ce: {message.text}')

# Wannan don Cyclic da Replit su gane yana raye
from flask import Flask
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

import threading
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

print("Bot ya fara aiki...")
bot.infinity_polling()
