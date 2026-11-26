"""
Instagram Group Chat Bot
Render Free Tier Compatible | Singapore Region
Uses instagrapi (unofficial Instagram Private API)
"""

import os
import time
import json
import logging
import threading
import schedule
from datetime import datetime, timedelta
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

# ─── Logging Setup ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("IGBot")

# ─── Config from Environment ──────────────────────────────────────────────────
IG_USERNAME   = os.environ.get("IG_USERNAME", "")
IG_PASSWORD   = os.environ.get("IG_PASSWORD", "")
SESSION_FILE  = "session.json"
DATA_FILE     = "bot_data.json"

# ─── Allowed Group IDs (max 3) ────────────────────────────────────────────────
# Comma-separated in env: "123456,789012,345678"
ALLOWED_GC_IDS_RAW = os.environ.get("ALLOWED_GC_IDS", "")
ALLOWED_GC_IDS = [g.strip() for g in ALLOWED_GC_IDS_RAW.split(",") if g.strip()][:3]

# ─── Admin User IDs (max 5) ───────────────────────────────────────────────────
# Comma-separated in env: "admin_user1,admin_user2"
ADMIN_USERNAMES_RAW = os.environ.get("ADMIN_USERNAMES", "")
ADMIN_USERNAMES = [u.strip() for u in ADMIN_USERNAMES_RAW.split(",") if u.strip()][:5]

# ─── Cooldown: 12 hours between welcome-back messages per user ───────────────
WELCOME_COOLDOWN_HOURS = 12

# ─── Instagram Link Pattern ───────────────────────────────────────────────────
import re
IG_LINK_PATTERN = re.compile(r"https?://(ig\.me|www\.instagram\.com|instagram\.com)/", re.IGNORECASE)
IGNORE_PATTERN  = re.compile(r"\bignore\b", re.IGNORECASE)
ADMIN_CMD_PATTERN = re.compile(r"^/send_gc\s+(.+)$", re.DOTALL)

# ─── Persistent Data ──────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_welcome": {},     # {thread_id: {user_id: timestamp}}
        "known_members": {},    # {thread_id: [user_id, ...]}
        "daily_stats": {}       # {date: {thread_id: {msgs: int, active_users: set, joined: int}}}
    }

def save_data(data: dict):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Save data error: {e}")

data = load_data()

# ─── Instagram Client ─────────────────────────────────────────────────────────
cl = Client()
cl.delay_range = [2, 5]   # random delay between requests (anti-ban)

# Set device to avoid NoneType parse errors on fresh login
cl.set_device({
    "app_version": "269.0.0.18.75",
    "android_version": 26,
    "android_release": "8.0.0",
    "dpi": "480dpi",
    "resolution": "1080x1920",
    "manufacturer": "OnePlus",
    "device": "ONEPLUS A3003",
    "model": "OnePlus3",
    "cpu": "qcom",
    "version_code": "314665256",
})
cl.set_user_agent()

def login():
    """Login with session reuse to avoid frequent logins."""
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            log.info("✅ Logged in via saved session")
            return
        except Exception as e:
            log.warning(f"Session load failed: {e}, fresh login...")
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        log.info("✅ Fresh login successful")
    except Exception as e:
        log.error(f"❌ Login failed: {e}")
        raise

def safe_send(thread_id: str, text: str):
    """Send message with retry logic."""
    for attempt in range(3):
        try:
            cl.direct_send(text, thread_ids=[thread_id])
            time.sleep(2)
            return True
        except LoginRequired:
            log.warning("Session expired, re-logging...")
            login()
        except ClientError as e:
            log.error(f"Send error (attempt {attempt+1}): {e}")
            time.sleep(5)
    return False

# ─── Helper: Check cooldown ───────────────────────────────────────────────────
def can_welcome_back(thread_id: str, user_id: str) -> bool:
    tid = str(thread_id)
    uid = str(user_id)
    now = datetime.now().timestamp()
    last = data["last_welcome"].get(tid, {}).get(uid, 0)
    return (now - last) >= (WELCOME_COOLDOWN_HOURS * 3600)

def mark_welcomed(thread_id: str, user_id: str):
    tid = str(thread_id)
    uid = str(user_id)
    if tid not in data["last_welcome"]:
        data["last_welcome"][tid] = {}
    data["last_welcome"][tid][uid] = datetime.now().timestamp()
    save_data(data)

# ─── Helper: Stats tracking ───────────────────────────────────────────────────
def track_message(thread_id: str, user_id: str):
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    uid = str(user_id)

    if today not in data["daily_stats"]:
        data["daily_stats"][today] = {}
    if tid not in data["daily_stats"][today]:
        data["daily_stats"][today][tid] = {"msgs": 0, "active_users": [], "joined": 0}

    stats = data["daily_stats"][today][tid]
    stats["msgs"] += 1
    if uid not in stats["active_users"]:
        stats["active_users"].append(uid)
    save_data(data)

def track_join(thread_id: str):
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    if today not in data["daily_stats"]:
        data["daily_stats"][today] = {}
    if tid not in data["daily_stats"][today]:
        data["daily_stats"][today][tid] = {"msgs": 0, "active_users": [], "joined": 0}
    data["daily_stats"][today][tid]["joined"] += 1
    save_data(data)

# ─── Commands ─────────────────────────────────────────────────────────────────
def cmd_menu() -> str:
    return (
        "╔══════════════════════════╗\n"
        "║      🤖 BOT COMMANDS      ║\n"
        "╚══════════════════════════╝\n\n"
        "📋 /menu → Sare commands list\n\n"
        "📊 /total → Aaj ka stats dekho\n"
        "   • Total messages\n"
        "   • Active members\n"
        "   • New joins\n\n"
        "🔒 Admin Only (DM me):\n"
        "   /send_gc <message>\n"
        "   → Bot GC pe message bhejega\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Auto Features:\n"
        "👋 Welcome back (12h cooldown)\n"
        "🆕 New member welcome\n"
        "🌙 12 AM Good Night\n"
        "☀️ 7 AM Good Morning\n"
        "😂 'ignore' word react\n"
        "🔗 IG link react"
    )

def cmd_total(thread_id: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    stats = data.get("daily_stats", {}).get(today, {}).get(tid)

    if not stats:
        return (
            f"📊 Aaj ka Stats ({today})\n"
            "━━━━━━━━━━━━━━━━\n"
            "Messages: 0\n"
            "Active Members: 0\n"
            "New Joins: 0\n"
            "Total Members: N/A"
        )

    msgs         = stats.get("msgs", 0)
    active_count = len(stats.get("active_users", []))
    joined       = stats.get("joined", 0)

    # Get total members in thread
    try:
        thread = cl.direct_thread(int(thread_id))
        total_members = len(thread.users) + 1  # +1 for bot itself
    except Exception:
        total_members = "N/A"

    return (
        f"📊 Aaj ka Stats ({today})\n"
        "━━━━━━━━━━━━━━━━\n"
        f"💬 Messages: {msgs}\n"
        f"✅ Active Members: {active_count}\n"
        f"🆕 New Joins: {joined}\n"
        f"👥 Total Members: {total_members}"
    )

# ─── Scheduled Messages ───────────────────────────────────────────────────────
def send_good_night():
    log.info("🌙 Sending Good Night...")
    for gc_id in ALLOWED_GC_IDS:
        safe_send(gc_id, "GOOD NIGHT USERS 😴\nSusu karke soo jana babu 💋\n@everyone")

def send_good_morning():
    log.info("☀️ Sending Good Morning...")
    for gc_id in ALLOWED_GC_IDS:
        safe_send(gc_id, "GOOD MORNING Ngas 🌞\nHow are you @everyone")

def run_scheduler():
    schedule.every().day.at("00:00").do(send_good_night)
    schedule.every().day.at("07:00").do(send_good_morning)
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─── Main Polling Loop ────────────────────────────────────────────────────────
processed_items = set()   # track already-handled message IDs

def handle_admin_dm(sender_username: str, text: str):
    """Handle /send_gc command from admin in DM."""
    if sender_username not in ADMIN_USERNAMES:
        return

    match = ADMIN_CMD_PATTERN.match(text.strip())
    if not match:
        return

    msg_to_send = match.group(1).strip()
    log.info(f"Admin {sender_username} → sending to GCs: {msg_to_send}")
    for gc_id in ALLOWED_GC_IDS:
        safe_send(gc_id, msg_to_send)

def process_thread(thread):
    """Process a single thread (GC or DM)."""
    tid = str(thread.id)
    is_group = thread.is_group

    # Only process allowed GCs (or DMs from admins)
    if is_group and tid not in ALLOWED_GC_IDS:
        return

    # Get current member list for this thread
    current_members = [str(u.pk) for u in thread.users]

    # Detect new members (joined since last check)
    if is_group:
        known = data["known_members"].get(tid, [])
        new_members = [uid for uid in current_members if uid not in known]

        for uid in new_members:
            # Find username
            try:
                user_info = cl.user_info(int(uid))
                uname = user_info.username
            except Exception:
                uname = f"user{uid}"

            log.info(f"New member in {tid}: @{uname}")
            safe_send(tid, f"Welcome to our GC @{uname}! 🎉🎊\nGlad to have you here! 💫")
            track_join(tid)
            time.sleep(2)

        # Update known members
        data["known_members"][tid] = current_members
        save_data(data)

    # Process recent messages
    for item in thread.messages:
        item_id = str(item.id)
        if item_id in processed_items:
            continue
        processed_items.add(item_id)

        # Skip bot's own messages
        try:
            bot_pk = cl.user_id
        except Exception:
            bot_pk = None

        sender_pk = str(item.user_id) if item.user_id else None
        if sender_pk and str(bot_pk) == sender_pk:
            continue

        # Only handle text messages
        if item.item_type != "text":
            continue

        text = item.text or ""

        # ── Admin DM: /send_gc command ─────────────────────────────────────
        if not is_group:
            # Find sender username
            for u in thread.users:
                if str(u.pk) == sender_pk:
                    handle_admin_dm(u.username, text)
                    break
            continue

        # ── Group Chat message handling ────────────────────────────────────
        # Find sender info
        sender_uname = None
        for u in thread.users:
            if str(u.pk) == sender_pk:
                sender_uname = u.username
                break
        if not sender_uname:
            sender_uname = f"user{sender_pk}"

        # Track stats
        track_message(tid, sender_pk)

        # ── Command: /menu ─────────────────────────────────────────────────
        if text.strip().lower() == "/menu":
            safe_send(tid, cmd_menu())
            continue

        # ── Command: /total ────────────────────────────────────────────────
        if text.strip().lower() == "/total":
            safe_send(tid, cmd_total(tid))
            continue

        # ── Trigger: "ignore" word ─────────────────────────────────────────
        if IGNORE_PATTERN.search(text):
            # Reply with swipe-style reply if possible, else normal
            safe_send(tid, f"@{sender_uname} AWW BACCHA ISSOKIEE MEIN HU NA APKE LIYE 🥹 💋")
            continue

        # ── Trigger: Instagram link ────────────────────────────────────────
        if IG_LINK_PATTERN.search(text):
            safe_send(tid, f"@{sender_uname} AWW TERE B44P KI BIWI KE PICS DE RHA HAI GC PE ? 🥰")
            continue

        # ── Welcome Back (12h cooldown) ────────────────────────────────────
        if can_welcome_back(tid, sender_pk):
            safe_send(tid, f"Welcome back to our GC @{sender_uname} how are you? 🎈")
            mark_welcomed(tid, sender_pk)

def polling_loop():
    """Main loop: poll Instagram for new messages."""
    log.info("🤖 Bot polling started...")
    poll_interval = 15   # seconds between each poll (Render-safe)

    while True:
        try:
            inbox = cl.direct_threads(amount=20, thread_message_limit=5)
            for thread in inbox:
                try:
                    process_thread(thread)
                except Exception as e:
                    log.error(f"Thread error ({thread.id}): {e}")

        except LoginRequired:
            log.warning("⚠️ Login required, re-logging...")
            try:
                login()
            except Exception as e:
                log.error(f"Re-login failed: {e}")
                time.sleep(60)

        except Exception as e:
            log.error(f"Polling error: {e}")
            time.sleep(30)

        time.sleep(poll_interval)

# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not IG_USERNAME or not IG_PASSWORD:
        log.error("❌ Set IG_USERNAME and IG_PASSWORD in environment!")
        exit(1)

    if not ALLOWED_GC_IDS:
        log.warning("⚠️ No ALLOWED_GC_IDS set — bot won't respond to any GC!")

    log.info(f"📌 Allowed GCs  : {ALLOWED_GC_IDS}")
    log.info(f"👑 Admins       : {ADMIN_USERNAMES}")

    # Login
    login()

    # Start scheduler in background thread
    sched_thread = threading.Thread(target=run_scheduler, daemon=True)
    sched_thread.start()
    log.info("⏰ Scheduler started (Good Night 12AM / Good Morning 7AM)")

    # Start polling
    polling_loop()
