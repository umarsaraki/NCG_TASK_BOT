import telebot
import os
from supabase import create_client, Client
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            # New user - give welcome bonus
            supabase.table('users').insert({
                "user_id": user_id,
                "username": message.from_user.username,
                "balance": WELCOME_BONUS,
                "referred_by": referrer_id
            }).execute()
            bot.send_message(user_id, f"🎁 Welcome Bonus: +{WELCOME_BONUS} points credited!")

            # Give bonus to referrer too
            if referrer_id:
                ref_user = supabase.table('users').select("balance").eq('user_id', referrer_id).execute()
                if len(ref_user.data) > 0:
                    new_bal = ref_user.data[0]['balance'] + REFERRAL_BONUS
                    supabase.table('users').update({"balance": new_bal}).eq('user_id', referrer_id).execute()
                    bot.send_message(referrer_id, f"🎉 You earned {REFERRAL_BONUS} points! Someone joined with your referral link.")
        show_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join(call):
    user_id = call.from_user.id
    if check_membership(user_id):
        user = supabase.table('users').select("*").eq('user_id', user_id).execute()
        if len(user.data) == 0:
            # Give welcome bonus only on first time
            referrer_id = None
            if 'referred_by' in call.message.text:
                pass
            supabase.table('users').insert({
                "user_id": user_id,
                "username": call.from_user.username,
                "balance": WELCOME_BONUS
            }).execute()
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
        if state == "waiting_payment":
            add_payment_data(message)
            return
        elif state == "waiting_withdraw":
            process_withdraw(message)
            return

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

    text = f"👥 **Your Referral Link**\n\n{ref_link}\n\nEarn **{REFERRAL_BONUS} points** for every person who joins with your link.\n\n**Total Referrals:** {count}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Copy Link", url=ref_link))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

def add_payment(message):
    user_states[message.from_user.id] = "waiting_payment"
    bot.reply_to(message, "Set your Bank Information:\n\nSend in this format:\n`Account Number | Account Name | Bank Name | Phone | Network`\n\nExample: `0123456789 | Musa Adamu | GTBank | 08012345678 | MTN`", parse_mode="Markdown")

def add_payment_data(message):
    try:
        parts = [p.strip() for p in message.text.split('|')]
        acc, name, bank, phone, network = parts
        supabase.table('users').update({
            "account_number": acc, "account_name": name, "bank_name": bank,
            "phone": phone, "network": network
        }).eq('user_id', message.from_user.id).execute()
        del user_states[message.from_user.id]
        bot.reply_to(message, "✅ Payment method saved successfully!")
    except:
        bot.reply_to(message, "❌ Wrong format. Send like: `Acc | Name | Bank | Phone | Network`", parse_mode="Markdown")

def withdraw(message):
    user = supabase.table('users').select("*").eq('user_id', message.from_user.id).execute().data[0]
    if not user.get('account_number'):
        bot.reply_to(message, "🚫 No payment method found.\nPlease go to `Add Payment` first")
        return
    user_states[message.from_user.id] = "waiting_withdraw"
    bot.reply_to(message, f"💸 Minimum withdrawal is {MIN_WITHDRAW} points\n\nEnter amount you want to withdraw:")

def process_withdraw(message):
    try:
        amount = int(message.text)
        user_id = message.from_user.id
        user = supabase.table('users').select("balance").eq('user_id', user_id).execute().data[0]
        balance = user['balance']

        if amount < MIN_WITHDRAW:
            bot.reply_to(message, f"❌ Insufficient. Minimum withdrawal is {MIN_WITHDRAW} points")
            return
        if amount > balance:
            bot.reply_to(message, f"❌ You only have {balance} points")
            return

        new_balance = balance - amount
        supabase.table('users').update({"balance": new_balance}).eq('user_id', user_id).execute()
        supabase.table('withdrawals').insert({"user_id": user_id, "amount": amount, "status": "pending", "requested_at": datetime.now().isoformat()}).execute()
        del user_states[user_id]
        bot.reply_to(message, f"✅ Withdrawal request of {amount} points submitted!\nAdmin will process it soon.")
        for admin in ADMIN_IDS:
            bot.send_message(admin, f"New Withdrawal Request:\nUser: {user_id}\nAmount: {amount}")
    except:
        bot.reply_to(message, "❌ Enter a valid number")

def history(message):
    tasks = supabase.table('user_tasks').select("*").eq('user_id', message.from_user.id).order('submitted_at', desc=True).execute()
    withdraws = supabase.table('withdrawals').select("*").eq('user_id', message.from_user.id).order('requested_at', desc=True).execute()

    text = "📜 **Your History:**\n\n"
    if len(tasks.data) > 0:
        text += "**Tasks:**\n"
        for t in tasks.data:
            status = "✅ Approved" if t['status'] == "approved" else "❌ Rejected" if t['status'] == "rejected" else "⏳ Pending"
            text += f"Task {t['task_id']} - {status}\n"

    if len(withdraws.data) > 0:
        text += "\n**Withdrawals:**\n"
        for w in withdraws.data:
            status = "✅ Paid" if w['status'] == "paid" else "⏳ Pending"
            text += f"{w['amount']} points - {status}\n"

    if len(tasks.data) == 0 and len(withdraws.data) == 0:
        text = "You have no history yet"
    bot.reply_to(message, text, parse_mode="Markdown")

def task(message):
    tasks = supabase.table('tasks').select("*").eq('active', True).execute()
    if len(tasks.data) == 0:
        bot.reply_to(message, "No available task")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for t in tasks.data:
        buttons.append(InlineKeyboardButton(f"Task {t['id']}", callback_data=f"view_task_{t['id']}"))
    markup.add(*buttons)
    bot.send_message(message.chat.id, "📋 Available Tasks:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_task_"))
def view_task(call):
    task_id = int(call.data.split('_')[2])
    t = supabase.table('tasks').select("*").eq('id', task_id).execute().data[0]
    text = f"**Task {t['id']}**: {t['title']}\nLink: {t['link']}\nPoints: {TASK_POINTS}\n\nTo submit: /submit {t['id']}"
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def leaderboard(message):
    month = datetime.now().strftime("%Y-%m")
    top = supabase.table('leaderboard').select("user_id, points_earned").eq('month_year', month).order('points_earned', desc=True).limit(10).execute()

    text = "🏆 **TOP 10 THIS MONTH** 🏆\n\n"
    for i, t in enumerate(top.data):
        pos = i+1
        prize = PRIZES.get(pos, 0)
        text += f"**TOP {pos}**: User `{t['user_id']}` - {t['points_earned']} pts\nPrize: {prize:,} Naira\n"

    if len(top.data) == 0:
        text = "No points earned this month yet"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['submit'])
def submit(message):
    try:
        task_id = int(message.text.split()[1])
        user_id = message.from_user.id
        check = supabase.table('user_tasks').select("*").eq('user_id', user_id).eq('task_id', task_id).execute()
        if len(check.data) > 0:
            bot.reply_to(message, "You already submitted this task")
            return
        pending_submissions[user_id] = task_id
        bot.reply_to(message, f"Send screenshot as proof for Task {task_id} 📸")
    except:
        bot.reply_to(message, "Usage: /submit 1")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if user_id not in pending_submissions: return
    task_id = pending_submissions[user_id]
    file_id = message.photo[-1].file_id
    username = message.from_user.username
    supabase.table('user_tasks').insert({"user_id": user_id, "username": username, "task_id": task_id, "screenshot_url": file_id, "status": "pending", "submitted_at": datetime.now().isoformat()}).execute()
    del pending_submissions[user_id]
    bot.reply_to(message, "Screenshot received! Admin will review ✅")

# ADMIN
@bot.message_handler(commands=['addtask'])
def add_task(message):
    if not is_admin(message.from_user.id): return
    try:
        parts = message.text.split('|')
        title, link = parts[0].replace('/addtask ', '').strip(), parts[1].strip()
        supabase.table('tasks').insert({"title": title, "link": link, "points": TASK_POINTS, "active": True}).execute()
        bot.reply_to(message, f"Task added: {title} - {TASK_POINTS} points")
    except:
        bot.reply_to(message, "Usage: /addtask Title | Link")

@bot.message_handler(commands=['pending'])
def pending_tasks(message):
    if not is_admin(message.from_user.id): return
    pending = supabase.table('user_tasks').select("*").eq('status', 'pending').execute()
    text = "📋 **Pending Submissions:**\n\n"
    for p in pending.data:
        text += f"User: `{p['user_id']}` @{p['username']}\nTask: `{p['task_id']}`\n/approve {p['user_id']} {p['task_id']} | /reject {p['user_id']} {p['task_id']}\n\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['approve'])
def approve_task(message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    uid, tid = int(parts[1]), int(parts[2])
    supabase.table('user_tasks').update({"status": "approved"}).eq('user_id', uid).eq('task_id', tid).execute()
    bal = supabase.table('users').select("balance").eq('user_id', uid).execute().data[0]['balance']
    supabase.table('users').update({"balance": bal + TASK_POINTS}).eq('user_id', uid).execute()
    month = datetime.now().strftime("%Y-%m")
    supabase.table('leaderboard').upsert({"user_id": uid, "points_earned": TASK_POINTS, "month_year": month}).execute()
    bot.reply_to(message, f"Approved! +{TASK_POINTS} points added")
    bot.send_message(uid, f"Task {tid} APPROVED! +{TASK_POINTS} points ✅")

@bot.message_handler(commands=['reject'])
def reject_task(message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    uid, tid = int(parts[1]), int(parts[2])
    supabase.table('user_tasks').update({"status": "rejected"}).eq('user_id', uid).eq('task_id', tid).execute()
    bot.reply_to(message, "Rejected")
    bot.send_message(uid, f"Task {tid} REJECTED ❌")

print("Bot is running...")
bot.polling(none_stop=True, interval=0)
