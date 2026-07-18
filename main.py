import telebot
import os
from supabase import create_client, Client
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin IDs - Both of you can approve and withdraw
ADMIN_IDS = [8552397401, 7544805601]

# This will hold users waiting to send screenshot
pending_submissions = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = supabase.table('users').select("*").eq('user_id', user_id).execute()
    if len(user.data) == 0:
        supabase.table('users').insert({"user_id": user_id, "balance": 0}).execute()
        bot.reply_to(message, "Welcome to NCG Bot! `🎉`\nUse /task to start earning points\nUse /balance to check your points")
    else:
        bot.reply_to(message, "Welcome back!")

@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    user = supabase.table('users').select("balance").eq('user_id', user_id).execute()
    if len(user.data) > 0:
        bal = user.data[0]['balance']
        bot.reply_to(message, f"💰 Your balance: {bal} points")
    else:
        bot.reply_to(message, "You don't have an account. Use /start first")

@bot.message_handler(commands=['task'])
def task(message):
    tasks = supabase.table('tasks').select("*").eq('active', True).execute()
    if len(tasks.data) == 0:
        bot.reply_to(message, "No tasks available right now. Check back later")
    else:
        text = "Available tasks:\n\n"
        for t in tasks.data:
            text += f"**Task {t['id']}**: {t['title']}\nLink: {t['link']}\nPoints: {t['points']}\n\n"
        text += "To submit: /submit `id_number`"
        bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['submit'])
def submit(message):
    try:
        task_id = int(message.text.split()[1])
        user_id = message.from_user.id

        task_check = supabase.table('tasks').select("*").eq('id', task_id).execute()
        if len(task_check.data) == 0:
            bot.reply_to(message, "This task does not exist")
            return

        check = supabase.table('user_tasks').select("*").eq('user_id', user_id).eq('task_id', task_id).execute()
        if len(check.data) > 0:
            bot.reply_to(message, "You have already completed this task")
            return

        pending_submissions[user_id] = task_id
        bot.reply_to(message, f"Now send screenshot for Task {task_id} here `📸`")

    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /submit 1")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id

    if user_id not in pending_submissions:
        bot.reply_to(message, "You haven't started any task. Use /submit 1 first")
        return

    task_id = pending_submissions[user_id]
    file_id = message.photo[-1].file_id

    supabase.table('user_tasks').insert({
        "user_id": user_id,
        "task_id": task_id,
        "screenshot_url": file_id,
        "status": "pending",
        "submitted_at": datetime.now().isoformat()
    }).execute()

    del pending_submissions[user_id]
    bot.reply_to(message, "Screenshot received! Admin will review and add your points `✅`")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    month = datetime.now().strftime("%Y-%m")
    top = supabase.table('leaderboard').select("user_id, points_earned").eq('month_year', month).order('points_earned', desc=True).limit(10).execute()

    if len(top.data) == 0:
        bot.reply_to(message, "No points earned this month yet")
        return

    text = "🏆 **Top 10 this month:**\n\n"
    for i, t in enumerate(top.data):
        text += f"{i+1}. User `{t['user_id']}` - {t['points_earned']} points\n"
    bot.reply_to(message, text, parse_mode="Markdown")

# ===== ADMIN COMMANDS =====
@bot.message_handler(commands=['pending'])
def pending_tasks(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "You are not authorized to use this command")
        return

    pending = supabase.table('user_tasks').select("*").eq('status', 'pending').execute()
    if len(pending.data) == 0:
        bot.reply_to(message, "No pending tasks")
        return

    text = "📋 **Pending Submissions:**\n\n"
    for p in pending.data:
        text += f"User: `{p['user_id']}` | Task: `{p['task_id']}`\nTo approve: /approve {p['user_id']} {p['task_id']}\n\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['approve'])
def approve_task(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "You are not authorized to use this command")
        return

    try:
        parts = message.text.split()
        target_user_id = int(parts[1])
        task_id = int(parts[2])

        submission = supabase.table('user_tasks').select("*").eq('user_id', target_user_id).eq('task_id', task_id).eq('status', 'pending').execute()
        if len(submission.data) == 0:
            bot.reply_to(message, "No pending submission found")
            return

        points = supabase.table('tasks').select("points").eq('id', task_id).execute().data[0]['points']

        supabase.table('user_tasks').update({"status": "approved"}).eq('user_id', target_user_id).eq('task_id', task_id).execute()

        current_balance = supabase.table('users').select("balance").eq('user_id', target_user_id).execute().data[0]['balance']
        supabase.table('users').update({"balance": current_balance + points}).eq('user_id', target_user_id).execute()

        month = datetime.now().strftime("%Y-%m")
        supabase.table('leaderboard').upsert({"user_id": target_user_id, "points_earned": points, "month_year": month}).execute()

        bot.reply_to(message, f"Approved! Added {points} points to User {target_user_id}")
        bot.send_message(target_user_id, f"Your Task {task_id} was approved! You earned {points} points `✅`")

    except:
        bot.reply_to(message, "Usage: /approve `user_id` `task_id`")

@bot.message_handler(commands=['withdraw'])
def withdraw_request(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "You are not authorized to use this command")
        return

    try:
        parts = message.text.split()
        target_user_id = int(parts[1])
        amount = int(parts[2])

        current_balance = supabase.table('users').select("balance").eq('user_id', target_user_id).execute().data[0]['balance']

        if current_balance < amount:
            bot.reply_to(message, f"User has only {current_balance} points. Not enough")
            return

        new_balance = current_balance - amount
        supabase.table('users').update({"balance": new_balance}).eq('user_id', target_user_id).execute()

        supabase.table('withdrawals').insert({
            "user_id": target_user_id,
            "amount": amount,
            "status": "paid",
            "requested_at": datetime.now().isoformat()
        }).execute()

        bot.reply_to(message, f"Withdrawn {amount} points from User {target_user_id}. New balance: {new_balance}")
        bot.send_message(target_user_id, f"Your withdrawal of {amount} points was processed `✅`")

    except:
        bot.reply_to(message, "Usage: /withdraw `user_id` `amount`")

print("Bot is running...")
bot.polling(none_stop=True, interval=0)
