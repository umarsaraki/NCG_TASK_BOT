import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from supabase import create_client, Client
from datetime import datetime
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

ADMIN_IDS = [8552397401, 7544805601]
CHANNEL_1 = "nigeriancapitalgrowth"
CHANNEL_2 = "royalempireupdate"
pending_submissions = {}
user_states = {}

MIN_WITHDRAW = 100
TASK_POINTS = 10
WELCOME_BONUS = 20
REFERRAL_BONUS = 20
PRIZES = {1: 50000, 2: 40000, 3: 30000, 4: 20000, 5: 15000, 6: 10000, 7: 8000, 8: 6000, 9: 4000, 10: 2000}

def is_admin(user_id):
    return user_id in ADMIN_IDS

def check_membership(user_id):
    try:
        m1 = bot.get_chat_member(CHANNEL_1, user_id).status
        m2 = bot.get_chat_member(CHANNEL_2, user_id).status
        return m1 in ['member', 'administrator', 'creator'] and m2 in ['member', 'administrator', 'creator']
    except:
        return False

def show_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💰 Balance", "📋 Task", "💳 Add Payment", "💸 Withdraw")
    markup.add("📜 History", "🏆 Leaderboard", "👥 Referral")
    bot.send_message(chat_id, "Welcome to NCG Bot! 🎉\nChoose an option below:", reply_markup=markup)

def force_join(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Join Channel 1", url="https://t.me/nigeriancapitalgrowth"))
    markup.add(InlineKeyboardButton("Join Channel 2", url="https://t.me/royalempireupdate"))
    markup.add(InlineKeyboardButton("✅ Channel Joined", callback_data="check_join"))
    bot.send_message(message.chat.id, "🚫 You must join both channels to use the bot:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 else None
    user_id = message.from_user.id
    if not check_membership(user_id):
        force_join(message)
    else:
        user = supabase.table('users').select("*").eq('user_id', user_id).execute()
        if len(user.data) == 0:
            supabase.table('users').insert({"user_id": user_id, "username": message.from_user.username, "balance": WELCOME_BONUS, "referred_by": referrer_id}).execute()
            bot.send_message(user_id, f"🎁 Welcome Bonus: +{WELCOME_BONUS} points credited!")
            if referrer_id:
                ref_user = supabase.table('users').select("balance").eq('user_id', referrer_id).execute()
                if len(ref_user.data) > 0:
                    new_bal = ref_user.data[0]['balance'] + REFERRAL_BONUS
                    supabase.table('users').update({"balance": new_bal}).eq('user_id', referrer_id).execute()
                    bot.send_message(referrer_id, f"🎉 You earned {REFERRAL_BONUS} points!")
        show_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join(call):
    user_id = call.from_user.id
    if check_membership(user_id):
        user = supabase.table('users').select("*").eq('user_id', user_id).execute()
        if len(user.data) == 0:
            supabase.table('users').insert({"user_id": user_id, "username": call.from_user.username, "balance": WELCOME_BONUS}).execute()
            bot.send_message(user_id, f"🎁 Welcome Bonus: +{WELCOME_BONUS} points credited!")
        show_menu(call.message.chat.id)
        bot.answer_callback_query(call.id, "Welcome! ✅")
    else:
        bot.answer_callback_query(call.id, "Please join both channels first", show_alert=True)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    if not check_membership(message.from_user.id):
        force_join(message)
        return
    user_id = message.from_user.id
    text = message.text
    if user_id in user_states:
        state = user_states[user_id]
        if state == "waiting_payment": add_payment_data(message); return
        elif state == "waiting_withdraw": process_withdraw(message); return
    if text == "💰 Balance": balance(message)
    elif text == "📋 Task": task(message)
    elif text == "💳 Add Payment": add_payment(message)
    elif text == "💸 Withdraw": withdraw(message)
    elif text == "📜 History": history(message)
    elif text == "🏆 Leaderboard": leaderboard(message)
    elif text == "👥 Referral": referral(message)

def balance(message):
    user = supabase.table('users').select("balance").eq('user_id', message.from_user.id).execute()
    bal = user.data[0]['balance'] if len(user.data) > 0 else 0
    bot.reply_to(message, f"💰 Your Balance: {bal} points")

def referral(message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    ref_count = supabase.table('users').select("user_id").eq('referred_by', user_id).execute()
    count = len(ref_count.data)
    text = f"👥 **Your Referral Link**\n\n{ref_link}\n\nEarn **{REFERRAL_BONUS} points** for every person who joins.\n\n**Total Referrals:** {count}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

def add_payment(message):
    user_states[message.from_user.id] = "waiting_payment"
    bot.reply_to(message, "Send: `Acc | Name | Bank | Phone | Network`", parse_mode="Markdown")

def add_payment_data(message):
    try:
        parts = [p.strip() for p in message.text.split('|')]
        acc, name, bank, phone, network = parts
        supabase.table('users').update({"account_number": acc, "account_name": name, "bank_name": bank, "phone": phone, "network": network}).eq('user_id', message.from_user.id).execute()
        del user_states[message.from_user.id]
        bot.reply_to(message, "✅ Payment method saved!")
    except:
        bot.reply_to(message, "❌ Wrong format.")

def withdraw(message):
    user = supabase.table('users').select("*").eq('user_id', message.from_user.id).execute().data[0]
    if not user.get('account_number'):
        bot.reply_to(message, "🚫 Add Payment first")
        return
    user_states[message.from_user.id] = "waiting_withdraw"
    bot.reply_to(message, f"Min withdrawal is {MIN_WITHDRAW} points\nEnter amount:")

def process_withdraw(message):
    try:
        amount = int(message.text)
        user_id = message.from_user.id
        user = supabase.table('users').select("balance").eq('user_id', user_id).execute().data[0]
        balance = user['balance']
        if amount < MIN_WITHDRAW: bot.reply_to(message, f"❌ Min is {MIN_WITHDRAW}"); return
        if amount > balance: bot.reply_to(message, f"❌ You have {balance}"); return
        supabase.table('users').update({"balance": balance - amount}).eq('user_id', user_id).execute()
        supabase.table('withdrawals').insert({"user_id": user_id, "amount": amount, "status": "pending", "requested_at": datetime.now().isoformat()}).execute()
        del user_states[user_id]
        bot.reply_to(message, f"✅ Withdrawal of {amount} submitted!")
        for admin in ADMIN_IDS: bot.send_message(admin, f"New Withdrawal:\nUser: {user_id}\nAmount: {amount}")
    except: bot.reply_to(message, "❌ Enter number")

def history(message): bot.reply_to(message, "📜 History feature is here")
def task(message): bot.reply_to(message, "📋 Task feature is here")
def leaderboard(message): bot.reply_to(message, "🏆 Leaderboard feature is here")

# WEBHOOK CODE DON RENDER
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "ok", 200

@app.route("/")
def webhook_test():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + BOT_TOKEN)
    return "Webhook set", 200

# Wannan layin gunicorn zai rike shi, don haka ba a buqatar app.run
