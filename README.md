🤖 Instagram GC Bot — Setup Guide

📁 Files

bot.py           ← Main bot code
requirements.txt ← Python dependencies
render.yaml      ← Render deploy config
README.md        ← This file

⚙️ Step 1 — Environment Variables

Render dashboard pe jaake ye 4 variables set karo:

Variable
Example Value
Description
IG_USERNAME
my_bot_account
Bot ka Instagram username
IG_PASSWORD
mypassword123
Bot ka Instagram password
ALLOWED_GC_IDS
123456,789012,345678
Group chat IDs (max 3, comma separated)
ADMIN_USERNAMES
admin1,admin2
Admin usernames (max 5, comma separated)

🔍 Step 2 — Group Chat ID kaise pata kare?

1. Bot account se GC open karo
2. Python mein ye run karo:
from instagrapi import Client
cl = Client()
cl.login("bot_username", "bot_password")

threads = cl.direct_threads(amount=20)
for t in threads:
    if t.is_group:
        print(f"GC Name: {t.thread_title} | ID: {t.id}")
3. Output mein apna GC ID copy karo → ALLOWED_GC_IDS mein daalo

🚀 Step 3 — Render pe Deploy

Option A — render.yaml se (Recommended)

1. GitHub pe repo banao, files push karo
2. Render → New → Blueprint → repo select karo
3. Environment variables set karo
4. Deploy!

Option B — Manual

1. Render → New Worker Service
2. Connect GitHub repo
3. Build Command: pip install -r requirements.txt
4. Start Command: python bot.py
5. Region: Singapore
6. Environment variables add karo
7. Deploy!

👑 Admin Commands (Bot ke DM mein bhejna)

/send_gc Hello everyone!

Bot ye message sare allowed GCs pe bhej dega.

📋 GC Commands

Command
Kaam
/menu
Sare commands aur features list
/total
Aaj ke messages, active users, new joins

🤖 Auto Features

Feature
Detail
Welcome back
Pehla message aane pe, 12h cooldown
New member welcome
Jab koi add ho GC mein
"ignore" word
Auto reply: AWW BACCHA...
Instagram link
Auto reply: B44P KI BIWI...
Good Night
Roz 12:00 AM
Good Morning
Roz 7:00 AM

⚠️ Important Notes

• Bot account alag hona chahiye (apna personal account mat use karo)
• 2FA disable karo bot account pe
• Bot ko GC mein add karo
• Render free tier pe bot 15 min baad sleep ho jata hai — isliye Worker use karo (web service nahi)
• Session file automatically save hoti hai re-login se bachne ke liye

🛡️ Limits (Built-in)

• Max 3 GCs (ALLOWED_GC_IDS mein sirf 3 IDs)
• Max 5 Admins (ADMIN_USERNAMES mein sirf 5)
• Welcome back: 12 hour cooldown per user per GC