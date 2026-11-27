"""
Instagram Group Chat Bot - Fixed Login Version
Render Free Tier | Singapore Region
"""

import os
import re
import time
import json
import logging
import threading
import traceback
import schedule
from datetime import datetime, timedelta
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("IGBot")

# ─── Environment Config ───────────────────────────────────────────────────────
IG_USERNAME      = os.environ.get("IG_USERNAME", "").strip()
IG_PASSWORD      = os.environ.get("IG_PASSWORD", "").strip()
IG_SESSION_ID    = os.environ.get("IG_SESSION_ID", "").strip()
SESSION_FILE     = "session.json"
DATA_FILE        = "bot_data.json"

if not IG_USERNAME or not IG_PASSWORD:
    log.error("Set IG_USERNAME and IG_PASSWORD in environment!")
    exit(1)

ALLOWED_GC_IDS_RAW = os.environ.get("ALLOWED_GC_IDS", "")
ALLOWED_GC_IDS = [g.strip() for g in ALLOWED_GC_IDS_RAW.split(",") if g.strip()][:3]

ADMIN_USERNAMES_RAW = os.environ.get("ADMIN_USERNAMES", "")
ADMIN_USERNAMES = [u.strip() for u in ADMIN_USERNAMES_RAW.split(",") if u.strip()][:5]

WELCOME_COOLDOWN_HOURS = 12

# ─── Patterns ─────────────────────────────────────────────────────────────────
IG_LINK_PATTERN   = re.compile(r"https?://(ig\.me|www\.instagram\.com|instagram\.com)/", re.IGNORECASE)
IGNORE_PATTERN    = re.compile(r"\bignore\b", re.IGNORECASE)
ADMIN_CMD_PATTERN = re.compile(r"^/send_gc\s+(.+)$", re.DOTALL)

# ─── Persistent Data ──────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_welcome": {},
        "known_members": {},
        "daily_stats": {}
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Save error: {e}")

data = load_data()

# ─── Instagram Client ─────────────────────────────────────────────────────────
cl = Client()
cl.delay_range = [2, 5]

def login():
    """Login to Instagram - tries session ID first, then password."""

    # Method 1: Session ID (most reliable, no challenge)
    if IG_SESSION_ID:
        try:
            log.info("Trying session ID login...")
            cl.login_by_sessionid(IG_SESSION_ID)
            log.info("✅ Logged in via session ID")
            return
        except Exception as e:
            log.warning(f"Session ID login failed: {e}")

    # Method 2: Saved session file
    if os.path.exists(SESSION_FILE):
        try:
            log.info("Trying saved session...")
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            log.info("✅ Logged in via saved session")
            return
        except Exception as e:
            log.warning(f"Saved session failed: {e}")
            try:
                os.remove(SESSION_FILE)
            except Exception:
                pass

    # Method 3: Fresh login with proper device
    log.info("Trying fresh login...")
    try:
        # Use a stable device fingerprint
        cl.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 28,
            "android_release": "9.0",
            "dpi": "420dpi",
            "resolution": "1080x2220",
            "manufacturer": "samsung",
            "device": "SM-G960F",
            "model": "dreamlte",
            "cpu": "samsungexynos9810",
            "version_code": "314665256",
        })
        cl.set_user_agent()
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        log.info("✅ Fresh login successful")
    except Exception as e:
        log.error(f"❌ All login methods failed: {e}")
        traceback.print_exc()
        raise

def safe_send(thread_id, text):
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

# ─── Welcome / Cooldown ───────────────────────────────────────────────────────
def can_welcome_back(thread_id, user_id):
    tid = str(thread_id)
    uid = str(user_id)
    last = data["last_welcome"].get(tid, {}).get(uid)
    if not last:
        return True
    diff = datetime.now() - datetime.fromisoformat(last)
    return diff > timedelta(hours=WELCOME_COOLDOWN_HOURS)

def mark_welcomed(thread_id, user_id):
    tid = str(thread_id)
    uid = str(user_id)
    if tid not in data["last_welcome"]:
        data["last_welcome"][tid] = {}
    data["last_welcome"][tid][uid] = datetime.now().isoformat()
    save_data(data)

# ─── Stats Tracking ───────────────────────────────────────────────────────────
def track_message(thread_id, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    uid = str(user_id)
    if today not in data["daily_stats"]:
        data["daily_stats"][today] = {}
    if tid not in data["daily_stats"][today]:
        data["daily_stats"][today][tid] = {"msgs": 0, "active_users": [], "joined": 0}
    data["daily_stats"][today][tid]["msgs"] += 1
    if uid not in data["daily_stats"][today][tid]["active_users"]:
        data["daily_stats"][today][tid]["active_users"].append(uid)
    save_data(data)

def track_join(thread_id):
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    if today not in data["daily_stats"]:
        data["daily_stats"][today] = {}
    if tid not in data["daily_stats"][today]:
        data["daily_stats"][today][tid] = {"msgs": 0, "active_users": [], "joined": 0}
    data["daily_stats"][today][tid]["joined"] += 1
    save_data(data)

# ─── Commands ─────────────────────────────────────────────────────────────────
def cmd_menu(thread_id):
    menu = (
        "📋 BOT COMMANDS & FEATURES:\n\n"
        "/menu — Ye list dikhata hai\n"
        "/total — Aaj ke stats dikhata hai\n\n"
        "🤖 AUTO FEATURES:\n"
        "• Welcome back — Purane member ka pehla message\n"
        "• New join — Naye member ko welcome\n"
        "• 'ignore' word detect — Special reply\n"
        "• Instagram link detect — Special reply\n"
        "• 12:00 AM — Good Night message\n"
        "• 7:00 AM — Good Morning message\n\n"
        "👑 ADMIN:\n"
        "• /send_gc <text> — DM me, sab GC pe bhejta hoon"
    )
    safe_send(thread_id, menu)

def cmd_total(thread_id):
    today = datetime.now().strftime("%Y-%m-%d")
    tid = str(thread_id)
    stats = data.get("daily_stats", {}).get(today, {}).get(tid, {})
    msgs        = stats.get("msgs", 0)
    active      = len(stats.get("active_users", []))
    joined      = stats.get("joined", 0)
    reply = (
        f"📊 TODAY'S STATS ({today}):\n\n"
        f"💬 Total Messages: {msgs}\n"
        f"👥 Active Members: {active}\n"
        f"🆕 New Joins: {joined}"
    )
    safe_send(thread_id, reply)

# ─── Scheduled Messages ───────────────────────────────────────────────────────
def send_good_night():
    msg = "GOOD NIGHT USERS 🌙\nSusu karke soo jana babu 💋 @everyone"
    for gid in ALLOWED_GC_IDS:
        safe_send(gid, msg)
    log.info("Good night sent")

def send_good_morning():
    msg = "GOOD MORNING Ngas ☀️\nHow are you @everyone"
    for gid in ALLOWED_GC_IDS:
        safe_send(gid, msg)
    log.info("Good morning sent")

# ─── Admin DM Handler ─────────────────────────────────────────────────────────
def handle_admin_dm(sender_username, text):
    match = ADMIN_CMD_PATTERN.match(text.strip())
    if not match:
        return
    gc_text = match.group(1).strip()
    sent = 0
    for gid in ALLOWED_GC_IDS:
        if safe_send(gid, gc_text):
            sent += 1
    log.info(f"Admin /send_gc: sent to {sent} GCs")

# ─── Thread Processor ─────────────────────────────────────────────────────────
seen_messages = set()

def process_thread(thread):
    tid = str(thread.id)

    # Only process allowed GCs
    if thread.is_group and tid not in ALLOWED_GC_IDS:
        return

    messages = thread.messages or []
    if not messages:
        return

    msg = messages[0]
    msg_id = str(msg.id)

    if msg_id in seen_messages:
        return
    seen_messages.add(msg_id)

    # Limit seen set size
    if len(seen_messages) > 2000:
        oldest = list(seen_messages)[:500]
        for m in oldest:
            seen_messages.discard(m)

    sender_id   = str(msg.user_id)
    text        = msg.text or ""
    msg_type    = msg.item_type

    # ── Admin DM ──────────────────────────────────────────────────────────────
    if not thread.is_group:
        try:
            user_info = cl.user_info(sender_id)
            uname = user_info.username
        except Exception:
            uname = ""
        if uname in ADMIN_USERNAMES and text.startswith("/send_gc"):
            handle_admin_dm(uname, text)
        return

    # ── Group Chat Processing ──────────────────────────────────────────────────
    tid_str = tid

    # Track message stats
    track_message(tid_str, sender_id)

    # Get sender username
    try:
        user_info = cl.user_info(sender_id)
        username = user_info.username
    except Exception:
        username = f"user_{sender_id}"

    # Check known members for welcome back
    if tid_str not in data["known_members"]:
        data["known_members"][tid_str] = []

    if sender_id not in data["known_members"][tid_str]:
        # First time we see this user
        data["known_members"][tid_str].append(sender_id)
        save_data(data)
    else:
        # Existing member — welcome back with cooldown
        if can_welcome_back(tid_str, sender_id):
            safe_send(tid_str, f"Welcome back to our GC @{username} how are you? 🎈")
            mark_welcomed(tid_str, sender_id)

    # /menu command
    if text.strip().lower() == "/menu":
        cmd_menu(tid_str)
        return

    # /total command
    if text.strip().lower() == "/total":
        cmd_total(tid_str)
        return

    # Instagram link trigger
    if IG_LINK_PATTERN.search(text):
        safe_send(tid_str, "AWW TERE B44P KI BIWI KE PICS DE RHA HAI GC PE ? 🥰")
        return

    # "ignore" word trigger
    if IGNORE_PATTERN.search(text):
        safe_send(tid_str, "AWW BACCHA ISSOKIEE MEIN HU NA APKE LIYE 🥹 💋")
        return

    # New member join event
    if msg_type == "action_log":
        action_text = str(text).lower()
        if "added" in action_text or "joined" in action_text:
            safe_send(tid_str, f"Welcome to our GC @{username} 🎉")
            track_join(tid_str)

# ─── Polling Loop ─────────────────────────────────────────────────────────────
def polling_loop():
    log.info("🤖 Bot polling started...")
    while True:
        try:
            threads = cl.direct_threads(amount=20)
            for thread in threads:
                try:
                    process_thread(thread)
                except Exception as e:
                    log.error(f"Thread error: {e}")
            time.sleep(15)
        except LoginRequired:
            log.warning("Login required, re-logging...")
            try:
                login()
            except Exception:
                time.sleep(60)
        except Exception as e:
            log.error(f"Polling error: {e}")
            time.sleep(30)

# ─── Scheduler ────────────────────────────────────────────────────────────────
def run_scheduler():
    schedule.every().day.at("00:00").do(send_good_night)
    schedule.every().day.at("07:00").do(send_good_morning)
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting Instagram GC Bot...")
    login()

    if not ALLOWED_GC_IDS:
        log.warning("⚠️  No ALLOWED_GC_IDS set — bot won't process any GCs!")

    if not ADMIN_USERNAMES:
        log.warning("⚠️  No ADMIN_USERNAMES set — admin commands disabled!")

    # Scheduler in background thread
    sched_thread = threading.Thread(target=run_scheduler, daemon=True)
    sched_thread.start()

    # Main polling loop
    polling_loop()
