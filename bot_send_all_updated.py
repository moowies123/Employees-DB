import urllib.parse
import uuid
import telebot
from telebot import types
import sqlite3
import shutil
import re
import os
import yt_dlp
import time
import random
import string
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
START_TIME = time.time()
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton 
from flask import Flask
from rapidfuzz import fuzz
from types import SimpleNamespace
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from google import genai
import json
from datetime import datetime, timedelta
from stats import *
from backup_system import *

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["TOKEN"]
TMDB_API_KEY = os.environ["TMDB_API_KEY"]

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={"api_version": "v1"}
)

ADMIN_ID = 1338207670
GROUP_ID = -1003876477799 #لجروب
RECOMMEND_CHANNEL_ID = -1003709621420  # حط ID قناة الترشيحات هنا
RECOMMEND_INTERVAL = 600               # 10 دقائق
CONTENT_CHANNEL_ID = -1002360047363 # ID القناة الخاصة
RECOMMEND_CHANNEL = -1003709621420
bot = telebot.TeleBot(TOKEN)
backup_conn = sqlite3.connect(
    DB_NAME,
    check_same_thread=False
)
from downloader import *

DB_NAME = "series.db"
BACKUP_FILE = "backup_series.db"

EPISODES_PER_PAGE = 8       # عدد الأزرار الرئيسية
EP_NUMBERS_PER_PAGE = 10     # عدد أرقام الحلقات في الصفحة
MAX_TRANSFERS = 15      # عدد التحويلات
TIME_WINDOW = 60          # خلال كام ثانية
AUTO_BLOCK = True         # False = إنذار بس
# 🧠 تخزين مؤقت لجلسات المستخدمين (pagination)
user_sessions = {}
series_sessions = {}
search_sessions = {}
confirm_sessions = {}
SERIES_CACHE = {}
CACHE_TTL = 300  # 5 دقائق
MOVIES_CACHE = {}
MOVIES_CACHE_TTL = 300  # 5 
USER_TRANSFERS = {}
BLOCKED_USERS = set()
private_search_mode = {}
LAST_NOTIFIED = {}
NOTIFICATIONS_ENABLED = True
RANGE_SESSIONS = {}
control_actions = {}
SUBS_NOTIFIED = {}
OWNER_USERNAME = "MohamedOwies"
SAVE_LOGS = {}
trend_sessions = {}
BLOCKED_SEARCH_USERS = {}
BATCH_VIDEOS = []
BATCH_TIMER = None
BATCH_WAIT_SECONDS = 5
BATCH_LOCK = threading.Lock()
WAITING_FOR_BATCH_NAME = False
movie_sessions = {}

# 🟢 جلب اسم البوت
bot_info = bot.get_me()
BOT_USERNAME = bot_info.username

def create_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # =========================================
    # 👤 USERS
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            user_id INTEGER PRIMARY KEY,

            username TEXT,

            first_name TEXT,

            join_date TEXT,

            is_blocked INTEGER DEFAULT 0
        )
    """)

    # =========================================
    # 🎬 EPISODES / MOVIES
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            series_name TEXT,

            episode_name TEXT,

            file_id TEXT UNIQUE,

            quality TEXT,

            media_type TEXT DEFAULT 'series',

            season INTEGER DEFAULT 1,

            episode INTEGER DEFAULT 0,

            release_year TEXT,

            views INTEGER DEFAULT 0,

            added_date TEXT,

            link_id TEXT
        )
    """)

    # =========================================
    # 🔗 LINKS
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            series_name TEXT,

            media_type TEXT DEFAULT 'series',

            link_id TEXT UNIQUE
        )
    """)

    # =========================================
    # 🖼️ SERIES CAPTIONS
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series_captions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            series_name TEXT UNIQUE,

            caption TEXT,

            photo_file_id TEXT,

            tmdb_id TEXT,

            poster TEXT,

            rating TEXT,

            genres TEXT,

            country TEXT,

            release_date TEXT,

            actors TEXT,

            director TEXT
        )
    """)

    # =========================================
    # 💳 SUBSCRIPTIONS
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (

            user_id INTEGER PRIMARY KEY,

            start_date TEXT,

            end_date TEXT,

            plan TEXT DEFAULT 'VIP'
        )
    """)

    # =========================================
    # 🎟 SUBSCRIPTION CODES
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscription_codes (

            code TEXT PRIMARY KEY,

            duration_days INTEGER,

            used INTEGER DEFAULT 0,

            used_by INTEGER,

            used_at TEXT
        )
    """)

    # =========================================
    # 📊 SEARCH HISTORY
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            query TEXT,

            search_date TEXT
        )
    """)

    # =========================================
    # ❤️ FAVORITES
    # =========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            series_name TEXT
        )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movie_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_name TEXT UNIQUE,
        posted_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    print("🟢 Database Ready")

def upgrade_database():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # =========================================
    # 👤 USERS TABLE
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            user_id INTEGER PRIMARY KEY,

            username TEXT,

            first_name TEXT,

            join_date TEXT,

            is_blocked INTEGER DEFAULT 0
        )
    """)

    # =========================================
    # 🎬 EPISODES UPGRADES
    # =========================================

    episode_columns = {

        "link_id": "TEXT",

        "quality": "TEXT",

        "media_type": "TEXT DEFAULT 'series'",

        "season": "INTEGER DEFAULT 1",

        "episode": "INTEGER DEFAULT 0",

        "release_year": "TEXT",

        "views": "INTEGER DEFAULT 0",

        "added_date": "TEXT"
    }

    for column, column_type in episode_columns.items():

        try:

            cursor.execute(
                f"ALTER TABLE episodes ADD COLUMN {column} {column_type}"
            )

            print(f"✅ Added {column} to episodes")

        except sqlite3.OperationalError:

            print(f"ℹ️ {column} already exists")

    # =========================================
    # 🔗 LINKS UPGRADES
    # =========================================

    try:

        cursor.execute("""
            ALTER TABLE links
            ADD COLUMN media_type TEXT DEFAULT 'series'
        """)

        print("✅ Added media_type to links")

    except sqlite3.OperationalError:

        print("ℹ️ media_type already exists in links")

    # =========================================
    # 🖼️ SERIES CAPTIONS TABLE
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series_captions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            series_name TEXT UNIQUE,

            caption TEXT,

            photo_file_id TEXT
        )
    """)

    captions_columns = {

        "tmdb_id": "TEXT",

        "poster": "TEXT",

        "rating": "TEXT",

        "genres": "TEXT",

        "country": "TEXT",

        "release_date": "TEXT",

        "actors": "TEXT",

        "director": "TEXT"
    }

    for column, column_type in captions_columns.items():

        try:

            cursor.execute(
                f"ALTER TABLE series_captions ADD COLUMN {column} {column_type}"
            )

            print(f"✅ Added {column} to series_captions")

        except sqlite3.OperationalError:

            print(f"ℹ️ {column} already exists")

    # =========================================
    # 💳 SUBSCRIPTIONS
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (

            user_id INTEGER PRIMARY KEY,

            start_date TEXT,

            end_date TEXT,

            plan TEXT DEFAULT 'VIP'
        )
    """)

    # =========================================
    # 🎟 SUBSCRIPTION CODES
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscription_codes (

            code TEXT PRIMARY KEY,

            months INTEGER,

            used INTEGER DEFAULT 0
        )
    """)

    sub_code_columns = {

        "duration_days": "INTEGER",

        "used_by": "INTEGER",

        "used_at": "TEXT"
    }

    for column, column_type in sub_code_columns.items():

        try:

            cursor.execute(
                f"ALTER TABLE subscription_codes ADD COLUMN {column} {column_type}"
            )

            print(f"✅ Added {column} to subscription_codes")

        except sqlite3.OperationalError:

            print(f"ℹ️ {column} already exists")

    # =========================================
    # 📊 SEARCH HISTORY
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            query TEXT,
            search_date TEXT
            
        )
    """)
    
    # =========================================
    # ❤️ FAVORITES
    # =========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            series_name TEXT
        )
    """)
    #Groub
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            title TEXT,
            added_date TEXT
            
        )
    
    
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backup_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER UNIQUE,
        backup_file TEXT,
        created_at TEXT
        )
   """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movie_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_name TEXT UNIQUE,
        posted_at TEXT
        )
   """)


    conn.commit()
    conn.close()
    print("🎬 movie_recommendations table ready")
    print("🟢 Database upgraded successfully") 

def link_old_series():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT series_name, link_id FROM links")
    links = cursor.fetchall()

    for series_name, link_id in links:
        cursor.execute(
            "UPDATE episodes SET link_id=? WHERE series_name=? AND link_id IS NULL",
            (link_id, series_name)
        )

    conn.commit()
    conn.close()
    print("✅ تم ربط كل المسلسلات القديمة باللينكات")

def clear_series_captions_once():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM series_captions;")
    conn.commit()
    conn.close()
    print("🧹 series_captions table cleared")


create_db()
upgrade_database()
link_old_series()

print("🟢 قاعدة البيانات جاهزة بكل الجداول المطلوبة.")

def extract_quality(text: str) -> str | None:
    if not text:
        return None

    text = str(text).lower()

    patterns = [
        ("2160p", r'\b(?:2160p?|4k)\b'),
        ("1080p", r'\b1080p?\b'),
        ("720p",  r'\b720p?\b'),
        ("480p",  r'\b480p?\b'),
        ("360p",  r'\b360p?\b'),
        ("240p",  r'\b240p?\b'),
        ("144p",  r'\b144p?\b'),
    ]

    for quality, pattern in patterns:
        if re.search(pattern, text, re.I):
            return quality

    return None

def clean_name(text):
    text = re.sub(r'@\S+', '', text)      # mentions
    text = re.sub(r'#\S+', '', text)      # hashtags
    text = re.sub(r'[|–_]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789"
)


def _normalize_parse_text(text: str) -> str:
    """تجهيز النص للتحليل فقط"""

    if not text:
        return ""

    text = str(text).strip()

    # تحويل الأرقام العربية إلى إنجليزية
    text = text.translate(ARABIC_DIGITS)

    # توحيد المسافات
    text = re.sub(r'\s+', ' ', text)

    return text
def parse_season_episode(text: str) -> dict:
    """
    Parser موحد للموسم والحلقة.

    يدعم:

    S5E16
    S05E16
    S5 E16
    S 5 E 16
    S5-E16
    S5_E16

    Season 5 Episode 16
    Season 5 Ep 16

    الموسم 5 الحلقة 16
    الموسم 5 الحلقه 16
    موسم 5 حلقة 16

    5x16
    05x16

    موسم فقط:
    S5
    Season 5
    الموسم 5
    جزء 5
    Part 5

    حلقة فقط:
    حلقة 5
    الحلقة 5
    الحلقه 5
    Episode 5
    Ep 5

    النتيجة:

    {
        "season": 5,
        "episode": 16
    }
    """

    text = _normalize_parse_text(text)

    if not text:
        return {
            "season": None,
            "episode": None
        }

    # ==================================================
    # 1️⃣ S5E16 / S05E16 / S 5 E 16
    # ==================================================

    match = re.search(
        r'\bs\s*(\d{1,2})\s*[-_. ]?\s*e\s*(\d{1,3})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": int(match.group(2))
        }

    # ==================================================
    # 2️⃣ 5x16 / 05x16
    # ==================================================

    match = re.search(
        r'\b(\d{1,2})\s*x\s*(\d{1,3})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": int(match.group(2))
        }

    # ==================================================
    # 3️⃣ Season 5 Episode 16
    # ==================================================

    match = re.search(
        r'\bseason\s*(\d{1,2})\s*'
        r'(?:episode|ep)\s*(\d{1,3})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": int(match.group(2))
        }

    # ==================================================
    # 4️⃣ الموسم 5 الحلقة 16
    # ==================================================

    match = re.search(
        r'(?:الموسم|موسم)\s*(\d{1,2})\s*'
        r'(?:الحلقة|الحلقه|حلقة)\s*(\d{1,3})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": int(match.group(2))
        }

    # ==================================================
    # 5️⃣ حلقة فقط
    # ==================================================

    match = re.search(
        r'(?:الحلقة|الحلقه|حلقة|episode|ep)\s*(\d{1,3})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": None,
            "episode": int(match.group(1))
        }

    # ==================================================
    # 6️⃣ الموسم فقط
    # ==================================================

    match = re.search(
        r'(?:الموسم|موسم)\s*(\d{1,2})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": None
        }

    # ==================================================
    # 7️⃣ Season 5
    # ==================================================

    match = re.search(
        r'\bseason\s*(\d{1,2})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": None
        }

    # ==================================================
    # 8️⃣ S5
    # ==================================================

    match = re.search(
        r'\bs\s*(\d{1,2})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": None
        }

    # ==================================================
    # 9️⃣ جزء / Part
    # ==================================================

    match = re.search(
        r'(?:جزء|الجزء|part)\s*(\d{1,2})\b',
        text,
        re.I
    )

    if match:
        return {
            "season": int(match.group(1)),
            "episode": None
        }

    # ==================================================
    # 🔟 لا يوجد موسم أو حلقة
    # ==================================================

    return {
        "season": None,
        "episode": None
    }


# ======================================================
# دوال التوافق مع الكود القديم
# ======================================================

def extract_season(text: str):
    """
    استخراج رقم الموسم.
    يستخدم الـ parser الموحد.
    """

    return parse_season_episode(text)["season"]


def extract_part(text: str):
    """
    استخراج رقم الجزء.
    متوافق مع الكود القديم.

    الجزء يعامل كموسم داخل النظام الحالي.
    """

    return parse_season_episode(text)["season"]


def extract_episode(text: str):
    """
    استخراج رقم الحلقة.
    """

    return parse_season_episode(text)["episode"]


def extract_episode_safe(text: str):
    """
    استخراج رقم الحلقة بشكل آمن.
    متوافق مع الكود القديم.
    """

    return parse_season_episode(text)["episode"]

def parse_caption(raw_caption):

    if not raw_caption:
        raw_caption = ""

    text = str(raw_caption).strip()

    # 🧠 تنظيف للجودة قبل التحليل
    clean_for_numbers = re.sub(
        r'(4k|2160p?|1080p?|720p?|480p?|360p?)',
        '',
        text,
        flags=re.I
    )

    # استخراج البيانات
    quality = extract_quality(text)
    season = extract_season(clean_for_numbers)
    episode = extract_episode(clean_for_numbers)
    part = extract_part(clean_for_numbers)

    # =========================
    # الاسم
    # =========================

    first_line = text.split("\n")[0].strip()
    clean = clean_series_title(first_line)
    base_name = get_base_series_name(clean)

    if not base_name:
        base_name = "Unknown"

    # =========================
    # الموسم النهائي
    # =========================

    final_season = season if season else part

    # =========================
    # الاسم النهائي للتخزين
    # =========================

    if final_season:
        series_name = f"{base_name} الموسم {final_season}"
    else:
        series_name = base_name

    # =========================
    # عنوان العرض
    # =========================

    title_parts = [base_name]

    if final_season is not None:
        title_parts.append(f"الموسم {final_season}")

    if episode is not None:
        title_parts.append(f"الحلقة {episode}")

    if quality:
        title_parts.append(str(quality))

    final_title = " - ".join(title_parts)

    # =========================
    # النوع
    # =========================

    content_type = "series" if episode is not None else "movie"

    return {
        "type": content_type,
        "series_name": series_name,
        "season": final_season,
        "episode": episode,
        "quality": quality,
        "final_title": final_title
    }

# ===== utils =====
def format_button_text(
    title: str,
    episode: int | None = None,
    quality: str | None = None,
    max_title_length: int = 18
) -> str:
    clean_title = title.strip()

    if len(clean_title) > max_title_length:
        clean_title = clean_title[:max_title_length - 1] + "…"

    parts = []

    if episode is not None:
        parts.append(f"ح{episode}")

    if quality:
        parts.append(quality.upper().replace(" ", ""))

    extra = " | ".join(parts)

    if extra:
        return f"📺 {clean_title} | {extra}"

    return f"🎬 {clean_title}"
    

def normalize(text):
    text = text.lower()
    replacements = {
        "أ": "ا", "إ": "ا", "آ": "ا",
        "ة": "ه", "ى": "ي",
        "ؤ": "و", "ئ": "ي"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # نشيل الرموز ونسيب المسافات
    text = re.sub(r'[^\w\s\u0600-\u06ff]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
    
def word_match(query, text):
    """
    مطابقة بالكلمات مش بالحروف
    لازم أغلب كلمات البحث تكون موجودة في الاسم
    """
    q_words = normalize(query).split()
    t_words = normalize(text).split()

    if not q_words or not t_words:
        return False

    matches = 0
    for w in q_words:
        if w in t_words:
            matches += 1

    # لازم على الأقل نصف كلمات البحث تكون موجودة
    return matches / len(q_words) >= 0.6


def normalize_series_name(name: str) -> str:
    if not name:
        return ""

    name = name.lower().strip()

    # إزالة المنشنات والهاشتاجات
    name = re.sub(r'@\S+', '', name)
    name = re.sub(r'#\S+', '', name)

    # توحيد الأرقام العربية → إنجليزية
    arabic_nums = "٠١٢٣٤٥٦٧٨٩"
    english_nums = "0123456789"
    trans = str.maketrans(arabic_nums, english_nums)
    name = name.translate(trans)

    # إزالة كلمات مالهاش لازمة
    junk_words = [
        "مسلسل", "فيلم", "الحلقة", "حلقة",
        "ep", "episode", "season", "part"
    ]
    for w in junk_words:
        name = re.sub(rf"\b{w}\b", "", name, flags=re.IGNORECASE)

    # إزالة أي رموز
    name = re.sub(r"[^a-z0-9\u0600-\u06FF ]+", "", name)

    # مسافات مظبوطة
    name = " ".join(name.split())

    return name


def get_series_name_for_caption(series_name: str):
    clean = normalize_series_name(series_name)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT series_name
        FROM series_captions
    """)

    rows = cursor.fetchall()
    conn.close()

    for (db_name,) in rows:
        if normalize_series_name(db_name) == clean:
            return db_name  # الاسم الصح اللي في الكابشن

    return None

def normalize_series_name(name):
    if not name:
        return ""

    return (
        name
        .replace("مسلسل", "")
        .replace("فيلم", "")
        .strip()
    )


def normalize_numbers(text: str) -> str:
    """
    يحول الأرقام العربية → إنجليزية
    """
    arabic_nums = "٠١٢٣٤٥٦٧٨٩"
    english_nums = "0123456789"

    for a, e in zip(arabic_nums, english_nums):
        text = text.replace(a, e)

    return text
# =========================
# 🧠 Helpers
# =========================
def is_year(num: int) -> bool:
    return 1900 <= num <= 2100
    
def smart_parse_query(text: str):
    if not text:
        return "", None

    text = normalize_numbers(text)

    text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)

    # ✅ استخراج الحلقة صح
    episode = extract_episode_safe(text)

    # حذف كلمة حلقة
    text = re.sub(
        r'(حلقة|الحلقه|ep|episode)\s*\d*',
        ' ',
        text,
        flags=re.I
    )

    # حذف الجودة بس
    text = re.sub(r'\b(360|480|720|1080)\b', ' ', text)

    text = re.sub(
        r'(الجودة|quality|حجم|size|ميجا|mb|gb)',
        ' ',
        text,
        flags=re.I
    )

    clean = normalize_series_name(text.strip())

    if not clean:
        return "", episode

    return clean, episode
    
def has_arabic(text: str) -> bool:
    return bool(re.search(r'[\u0600-\u06FF]', text))

def clean_series_title(name: str) -> str:
    """
    تنظيف اسم المسلسل أو الفيلم بشكل احترافي بدون مسح الموسم/الحلقة/الجزء
    """

    if not name:
        return ""

    text = name.lower()

    # حذف أي شيء بين () أو []
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]', '', text)

    # حذف الجودة
    text = re.sub(
        r'(4k|2160p?|1080p?|720p?|480p?|360p?|144p?|fhd|hd|sd)',
        '',
        text
    )

    # حذف صيغ release info
    text = re.sub(
        r'(bluray|webrip|web-dl|hdrip|dvdrip|x264|x265)',
        '',
        text
    )

    # استبدال الرموز بمسافة
    text = re.sub(r'[._\-]+', ' ', text)

    # حذف المسافات الزائدة
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def get_base_series_name(name: str) -> str:
    """
    استخراج الاسم الأساسي للمسلسل.

    يحذف:
    - الجودة
    - الموسم
    - الحلقة
    - S01E05
    - 1x05
    - الجزء
    """

    if not name:
        return ""

    text = _normalize_parse_text(name)

    # ==================================================
    # الجودة
    # ==================================================

    text = re.sub(
        r'\b(?:4k|2160p?|1080p?|720p?|480p?|360p?|240p?|144p?|fhd|hd|sd)\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # S05E16 / S5 E16 / S 5 E 16
    # ==================================================

    text = re.sub(
        r'\bs\s*\d{1,2}\s*[-_. ]?\s*e\s*\d{1,3}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # 5x16
    # ==================================================

    text = re.sub(
        r'\b\d{1,2}\s*x\s*\d{1,3}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # Season 5 Episode 16
    # ==================================================

    text = re.sub(
        r'\bseason\s*\d{1,2}\s*(?:episode|ep)\s*\d{1,3}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # الموسم 5 الحلقة 16
    # ==================================================

    text = re.sub(
        r'(?:الموسم|موسم)\s*\d{1,2}\s*'
        r'(?:الحلقة|الحلقه|حلقة)\s*\d{1,3}',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # الموسم فقط
    # ==================================================

    text = re.sub(
        r'(?:الموسم|موسم)\s*\d{1,2}',
        '',
        text,
        flags=re.I
    )

    text = re.sub(
        r'\bseason\s*\d{1,2}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # S5 فقط
    # ==================================================

    text = re.sub(
        r'\bs\s*\d{1,2}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # جزء / Part
    # ==================================================

    text = re.sub(
        r'(?:الجزء|جزء|part)\s*\d{1,2}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # الحلقة العادية
    # ==================================================

    text = re.sub(
        r'(?:الحلقة|الحلقه|حلقة|episode|ep)\s*\d{1,3}\b',
        '',
        text,
        flags=re.I
    )

    # ==================================================
    # تنظيف
    # ==================================================

    text = re.sub(r'[_\-.]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    text = text.strip(' -_.')

    return normalize_series_name(text)

def extract_year(text):
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if match:
        return match.group(1)
    return None

def extract_series_from_caption(caption: str) -> str:
    if not caption:
        return None

    # خد أول سطر بس
    first_line = caption.strip().split('\n')[0]

    # شيل الإيموجي 🎬
    first_line = first_line.replace("🎬", "").strip()

    # شيل أي جودة أو حجم لو لسه موجودين
    first_line = re.sub(
        r'(⚙️.*|💾.*)',
        '',
        first_line
    )

    return normalize_series_name(first_line)

def get_series_caption_fuzzy(cursor, detected_name):
    key = normalize_series_name(detected_name)

    cursor.execute("""
        SELECT series_name, photo_file_id, caption
        FROM series_captions
    """)

    rows = cursor.fetchall()

    for s_name, photo_id, caption in rows:
        db_key = normalize_series_name(s_name)

        if db_key in key or key in db_key:
            return photo_id, caption

    return None, None

def safe_markdown(text: str):
    if not text:
        return None

    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")

    return text


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


# ----------------------------
# تنظيف الاسم
# ----------------------------

def clean_query(title: str):

    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\[.*?\]', '', title)

    title = re.sub(
        r'(حلقة|episode|ep|season|موسم|جزء|part)\s*\d+',
        '',
        title,
        flags=re.I
    )

    title = re.sub(
        r'(720p|1080p|480p|360p|4k|hd)',
        '',
        title,
        flags=re.I
    )

    title = re.sub(r'\s+', ' ', title)

    return title.strip()


# ----------------------------
# البحث
# ----------------------------

def search_tmdb(title, is_series=True):

    query = clean_query(title)

    if not query:
        return None

    try:

        # =========================================
        # 🔍 SEARCH
        # =========================================

        endpoint = "/search/tv" if is_series else "/search/movie"

        search_url = BASE_URL + endpoint

        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "ar"
        }

        r = requests.get(
            search_url,
            params=params,
            timeout=10
        )

        data = r.json()

        if not data.get("results"):
            return None

        result = data["results"][0]

        tmdb_id = result["id"]

        # =========================================
        # 📄 DETAILS
        # =========================================

        details_endpoint = (
            f"/tv/{tmdb_id}"
            if is_series
            else f"/movie/{tmdb_id}"
        )

        details_url = BASE_URL + details_endpoint

        details_params = {
            "api_key": TMDB_API_KEY,
            "language": "ar"
        }

        details_r = requests.get(
            details_url,
            params=details_params,
            timeout=10
        )

        details = details_r.json()

        # =========================================
        # 🎭 CREDITS
        # =========================================

        credits_url = (
            BASE_URL +
            (
                f"/tv/{tmdb_id}/credits"
                if is_series
                else f"/movie/{tmdb_id}/credits"
            )
        )

        credits_r = requests.get(
            credits_url,
            params={
                "api_key": TMDB_API_KEY,
                "language": "ar"
            },
            timeout=10
        )

        credits = credits_r.json()

        # =========================================
        # 🖼️ POSTER
        # =========================================

        poster = None

        if details.get("poster_path"):

            poster = (
                IMAGE_BASE +
                details["poster_path"]
            )

        # =========================================
        # 🎭 GENRES
        # =========================================

        genres = ", ".join(
            [
                g["name"]
                for g in details.get("genres", [])
            ]
        )

        if not genres:
            genres = "غير معروف"

        # =========================================
        # 🌍 COUNTRY
        # =========================================

        if is_series:

            country = ", ".join(
                details.get("origin_country", [])
            )

        else:

            country = ", ".join(
                [
                    c["name"]
                    for c in details.get(
                        "production_countries",
                        []
                    )
                ]
            )

        if not country:
            country = "غير معروف"

        # =========================================
        # 🗣️ LANGUAGE
        # =========================================

        language = details.get(
            "original_language",
            "غير معروف"
        )

        # =========================================
        # ⏱️ RUNTIME
        # =========================================

        runtime = "غير معروف"

        if is_series:

            ep_time = details.get(
                "episode_run_time",
                []
            )

            if ep_time:

                runtime = f"{ep_time[0]} دقيقة"

        else:

            movie_runtime = details.get("runtime")

            if movie_runtime:

                runtime = f"{movie_runtime} دقيقة"

        # =========================================
        # 🎬 DIRECTOR
        # =========================================

        director = "غير معروف"

        for crew in credits.get("crew", []):

            if crew.get("job") == "Director":

                director = crew.get("name")

                break

        # =========================================
        # 👥 ACTORS
        # =========================================

        actors_list = []

        for actor in credits.get("cast", [])[:5]:

            actors_list.append(
                actor.get("name")
            )

        actors = (
            ", ".join(actors_list)
            if actors_list
            else "غير معروف"
        )

        # =========================================
        # 📅 DATE
        # =========================================

        release_date = (
            details.get("first_air_date")
            or details.get("release_date")
            or "غير معروف"
        )

        # =========================================
        # ⭐ RATING
        # =========================================

        rating = details.get(
            "vote_average",
            "N/A"
        )

        # =========================================
        # 📝 OVERVIEW
        # =========================================

        overview = details.get(
            "overview",
            "لا توجد قصة."
        )

        # =========================================
        # ✅ RETURN
        # =========================================

        return {

            "tmdb_id": tmdb_id,

            "name": (
                details.get("name")
                or details.get("title")
            ),

            "overview": overview,

            "rating": rating,

            "date": release_date,

            "poster": poster,

            "genres": genres,

            "country": country,

            "director": director,

            "runtime": runtime,

            "language": language,

            "actors": actors
        }

    except Exception as e:

        print("TMDB ERROR:", e)

        return None
    
def get_caption_with_fallback(cursor, title, media_type="series"):

    """
    جلب تفاصيل احترافية للفيلم/المسلسل
    1️⃣ DB exact
    2️⃣ TMDB كامل
    3️⃣ DB fuzzy
    """

    clean_title = get_base_series_name(title)

    # =========================================
    # 1️⃣ EXACT MATCH
    # =========================================

    row = get_series_caption_exact(cursor, clean_title)

    if row and row[0]:

        print("FROM DB EXACT:", clean_title)

        return row[0], row[1]

    # =========================================
    # 2️⃣ TMDB
    # =========================================

    is_series = media_type in ["series", "tv"]

    data = search_tmdb(clean_title, is_series)

    if data and data.get("poster"):
        poster = data.get("poster")
        name = data.get("name", clean_title)
        rating = data.get("rating", "غير متوفر")
        date = data.get("date", "غير متوفر")
        actors = data.get("actors", "غير متوفر")
        overview = data.get("overview", "غير متوفر")
        genres = data.get("genres", "غير متوفر")
        country = data.get("country", "غير متوفر")
        director = data.get("director", "غير متوفر")
        runtime = data.get("runtime", "غير متوفر")
        language = data.get("language", "غير متوفر")
        caption = f"""
🎬 {name}
⭐ التقييم : {rating}
📅 سنة الإنتاج : {date}
🌍 البلد : {country}
🎭 التصنيف : {genres}
🎬 المخرج : {director}
👥 البطولة :
{actors}
⏱️ المدة : {runtime}
🗣️ اللغة : {language}
📝 القصة :

{overview}
"""

        save_series_caption(
            cursor,
            clean_title,
            poster,
            caption
        )

        print("FROM TMDB:", clean_title)

        return poster, caption

    # =========================================
    # 3️⃣ FUZZY MATCH
    # =========================================

    row = get_series_caption_fuzzy(cursor, clean_title)

    if row and row[0]:

        print("FROM DB FUZZY:", clean_title)

        return row[0], row[1]

    print("NO DATA:", clean_title)

    return None, None

def get_series_caption_exact(cursor, title):

    clean_title = get_base_series_name(title)

    row = cursor.execute(
        """
        SELECT photo_file_id, caption
        FROM series_captions
        WHERE series_name = ?
        """,
        (clean_title,)
    )

    return row.fetchone()



def save_series_caption(cursor, title, poster, caption):

    clean_title = get_base_series_name(title)

    cursor.execute(
        """
        INSERT OR REPLACE INTO series_captions
        (series_name, photo_file_id, caption)
        VALUES (?, ?, ?)
        """,
        (
            clean_title,
            poster,
            caption
        )
        )

def check_transfer(user):
    user_id = user.id
    now = time.time()

    if user_id in BLOCKED_USERS:
        return False

    data = USER_TRANSFERS.get(user_id)

    if not data:
        USER_TRANSFERS[user_id] = {
            "count": 1,
            "start": now
        }
        return True

    if now - data["start"] > TIME_WINDOW:
        data["count"] = 1
        data["start"] = now
        return True

    data["count"] += 1

    if data["count"] >= MAX_TRANSFERS:
        alert_admin(user, data["count"])

        if AUTO_BLOCK:
            BLOCKED_USERS.add(user_id)

        return False

    return True
def alert_admin(user, count):
    text = (
        "🚨 *إنذار تحويلات*\n\n"
        f"👤 الاسم: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Username: @{user.username}\n"
        f"📊 التحويلات: {count}\n"
        f"⛔ الحالة: {'تم الحظر' if AUTO_BLOCK else 'إنذار فقط'}"
    )

    bot.send_message(
        ADMIN_ID,
        text,
        parse_mode="Markdown"
    )



def check_subscriptions_expiry():

    if not hasattr(check_subscriptions_expiry, "SUBS_NOTIFIED"):
        check_subscriptions_expiry.SUBS_NOTIFIED = {}

    SUBS_NOTIFIED = check_subscriptions_expiry.SUBS_NOTIFIED

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT user_id, end_date FROM subscriptions")
    users = cursor.fetchall()

    now_dt = datetime.now()
    now_ts = time.time()

    for user_id, end_date in users:

        try:

            expiry_date = datetime.fromisoformat(end_date)

            delta = expiry_date - now_dt

            days_left = delta.days

            key = f"{user_id}_{days_left}"

            if key in SUBS_NOTIFIED:
                if now_ts - SUBS_NOTIFIED[key] < 43200:
                    continue

            markup = InlineKeyboardMarkup()

            markup.add(
                InlineKeyboardButton(
                    "✨ تواصل للتجديد",
                    url=f"https://t.me/{OWNER_USERNAME}",style="primary"
                )
            )

            if days_left == 3:

                bot.send_message(
                    user_id,
                    "⏳ فاضل 3 أيام على انتهاء الاشتراك 🔥",
                    reply_markup=markup
                )

                SUBS_NOTIFIED[key] = now_ts

            elif days_left == 1:

                bot.send_message(
                    user_id,
                    "🚨 فاضل يوم واحد فقط على انتهاء الاشتراك",
                    reply_markup=markup
                )

                SUBS_NOTIFIED[key] = now_ts

            elif days_left <= 0:

                bot.send_message(
                    user_id,
                    "جدد اشتراكك علشان تقدر تشوف المسلسلاات واافلام براحتك❤️",
                    reply_markup=markup,
                    style="primary"
                )

                SUBS_NOTIFIED[key] = now_ts

        except Exception as e:
            print("Expiry Error:", e)

    conn.close()

def expiry_loop():
    while True:
        check_subscriptions_expiry()
        time.sleep(86400)  # كل يوم

# =========================================================
# 🎬 GET RANDOM MOVIE
# =========================================================

def get_random_movie():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:

        # =====================================================
        # 🛡️ STRICT MOVIE FILTER
        # أي علامة تشير لمسلسل / حلقة / موسم = رفض فوري
        # =====================================================

        def is_strict_movie(series_name, episode_name):

            text = f"{series_name or ''} {episode_name or ''}".strip()

            if not text:
                return False

            # -------------------------------------------------
            # تنظيف النص
            # -------------------------------------------------

            normalized = text.lower()

            normalized = re.sub(
                r'[_\-./]+',
                ' ',
                normalized
            )

            normalized = re.sub(
                r'\s+',
                ' ',
                normalized
            ).strip()

            # =================================================
            # 🇪🇬 كلمات عربية ممنوعة
            # =================================================

            forbidden_arabic = [
                "مسلسل",
                "المسلسل",
                "حلقة",
                "الحلقة",
                "حلقه",
                "الحلقه",
                "موسم",
                "الموسم",
                "جزء",
                "الجزء",
                "الحلقات",
                "حلقات",
                "مسلسلات"
            ]

            for word in forbidden_arabic:

                if word in normalized:
                    return False

            # =================================================
            # 🇬🇧 كلمات إنجليزية ممنوعة
            # =================================================

            forbidden_english = [
                "series",
                "season",
                "episode",
                "episodes",
                "ep",
                "s01",
                "s02",
                "s03",
                "s04",
                "s05"
            ]

            # كلمات كاملة فقط
            for word in forbidden_english:

                if re.search(
                    rf'(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])',
                    normalized,
                    re.IGNORECASE
                ):
                    return False

            # =================================================
            # 🔥 S01E01
            # S1E1
            # S01 E01
            # S01-E01
            # S01.E01
            # =================================================

            if re.search(
                r'(?<![a-z0-9])s\d+\s*e\d+(?![a-z0-9])',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 SE01
            # SE1
            # SE02 EP03
            # =================================================

            if re.search(
                r'(?<![a-z0-9])se\d+(?![a-z0-9])',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 E01 / E1 / E100
            # =================================================

            if re.search(
                r'(?<![a-z0-9])e\d+(?![a-z0-9])',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 EP01 / EP1 / EP100
            # =================================================

            if re.search(
                r'(?<![a-z0-9])ep\d+(?![a-z0-9])',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 S01 / S1 / S100
            # =================================================

            if re.search(
                r'(?<![a-z0-9])s\d+(?![a-z0-9])',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 Season 1 / Season01
            # =================================================

            if re.search(
                r'(?<![a-z0-9])season\s*\d*',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 Episode 1 / Episode01
            # =================================================

            if re.search(
                r'(?<![a-z0-9])episode\s*\d*',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 Part 1 / Part01
            # =================================================

            if re.search(
                r'(?<![a-z0-9])part\s*\d+',
                normalized,
                re.IGNORECASE
            ):
                return False

            # =================================================
            # 🔥 علامات الحلقات الشائعة
            # =================================================

            episode_patterns = [

                # 1x01
                r'(?<![a-z0-9])\d+x\d+(?![a-z0-9])',

                # 01x02
                r'(?<![a-z0-9])\d{1,3}\s*x\s*\d{1,3}(?![a-z0-9])',

                # 01 - 02 / 01.02
                r'(?<![a-z0-9])\d{1,3}\s*[-.]\s*\d{1,3}(?![a-z0-9])'
            ]

            for pattern in episode_patterns:

                if re.search(
                    pattern,
                    normalized,
                    re.IGNORECASE
                ):
                    return False

            # =================================================
            # 🔥 كلمات عربية مرتبطة بالمواسم والأجزاء
            # =================================================

            arabic_patterns = [

                r'موسم\s*\d+',
                r'الموسم\s*\d+',

                r'جزء\s*\d+',
                r'الجزء\s*\d+',

                r'حلقة\s*\d+',
                r'الحلقة\s*\d+',

                r'حلقه\s*\d+',
                r'الحلقه\s*\d+'
            ]

            for pattern in arabic_patterns:

                if re.search(
                    pattern,
                    normalized,
                    re.IGNORECASE
                ):
                    return False

            # =================================================
            # 🟢 اجتاز كل الاختبارات
            # =================================================

            return True

        # =====================================================
        # 🎬 قراءة المحتوى
        # =====================================================

        cursor.execute("""
            SELECT
                id,
                series_name,
                episode_name,
                quality
            FROM episodes
        """)

        rows = cursor.fetchall()

        if not rows:

            print(
                "❌ EPISODES TABLE IS EMPTY",
                flush=True
            )

            return None

        movies = {}

        rejected = 0

        # =====================================================
        # 🔎 فلترة المحتوى
        # =====================================================

        for ep_id, series_name, episode_name, quality in rows:

            if not series_name:
                continue

            series_name_clean = str(
                series_name
            ).strip()

            episode_name_clean = str(
                episode_name or ""
            ).strip()

            if not series_name_clean:
                continue

            # =================================================
            # 🛡️ STRICT CHECK
            # =================================================

            if not is_strict_movie(
                series_name_clean,
                episode_name_clean
            ):

                rejected += 1
                continue

            # =================================================
            # 🎬 الفيلم
            # =================================================

            movie_name = series_name_clean

            # فيلم واحد فقط من كل اسم
            if movie_name not in movies:

                movies[movie_name] = (
                    ep_id,
                    movie_name,
                    quality or "HD"
                )

        # =====================================================
        # 📊 إحصائيات
        # =====================================================

        movies = list(
            movies.values()
        )

        print(
            f"🎬 STRICT MOVIES: {len(movies)}",
            flush=True
        )

        print(
            f"🚫 REJECTED CONTENT: {rejected}",
            flush=True
        )

        if not movies:

            print(
                "❌ NO STRICT MOVIES FOUND",
                flush=True
            )

            return None

        # =====================================================
        # 🧠 الأفلام المرشحة سابقًا
        # =====================================================

        cursor.execute("""
            SELECT movie_name
            FROM movie_recommendations
        """)

        posted = {
            str(row[0]).strip()
            for row in cursor.fetchall()
            if row[0]
        }

        available = [
            movie
            for movie in movies
            if movie[1] not in posted
        ]

        print(
            f"🎬 ALREADY POSTED: {len(posted)}",
            flush=True
        )

        print(
            f"🎬 AVAILABLE MOVIES: {len(available)}",
            flush=True
        )

        # =====================================================
        # 🔄 دورة جديدة
        # =====================================================

        if not available:

            print(
                "🔄 ALL MOVIES WERE RECOMMENDED",
                flush=True
            )

            cursor.execute("""
                DELETE FROM movie_recommendations
            """)

            conn.commit()

            available = movies

        # =====================================================
        # ❌ لا يوجد محتوى
        # =====================================================

        if not available:

            print(
                "❌ NO AVAILABLE MOVIES",
                flush=True
            )

            return None

        # =====================================================
        # 🎯 اختيار عشوائي
        # =====================================================

        selected = random.choice(
            available
        )

        print(
            "🎯 SELECTED MOVIE:",
            selected[1],
            flush=True
        )

        print(
            "🆔 EPISODE ID:",
            selected[0],
            flush=True
        )

        return selected

    except Exception as e:

        print(
            "❌ GET RANDOM MOVIE ERROR:",
            repr(e),
            flush=True
        )

        return None

    finally:

        conn.close()

# =========================================================
# 📢 PUBLISH MOVIE RECOMMENDATION
# =========================================================

def publish_movie_recommendation():

    print(
        "🔥 publish_movie_recommendation() CALLED"
    )

    movie = get_random_movie()

    if not movie:

        print(
            "❌ NO MOVIE AVAILABLE FOR RECOMMENDATION"
        )

        return False

    ep_id, movie_name, quality = movie

    print(
        f"🎬 PREPARING RECOMMENDATION: {movie_name}"
    )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:

        # -------------------------------------------------
        # نجيب البوستر والكابشن
        # -------------------------------------------------

        caption_data = get_caption_with_fallback(
            cursor,
            movie_name,
            media_type="movie"
        )

        photo_id = None
        caption_text = None

        if caption_data:

            photo_id, caption_text = caption_data

        # -------------------------------------------------
        # لو مفيش Caption
        # -------------------------------------------------

        if not caption_text:

            caption_text = (
                f"🎬 *{safe_markdown(movie_name)}*"
            )

        # -------------------------------------------------
        # الزر
        # -------------------------------------------------

        markup = InlineKeyboardMarkup(
            row_width=1
        )

        markup.add(
            InlineKeyboardButton(
                "🎬 شوف الفيلم",
                url=(
                    f"https://t.me/"
                    f"{BOT_USERNAME}"
                    f"?start=rec_{ep_id}"
                ),
                style="primary"
            )
        )

        sent_successfully = False

        # -------------------------------------------------
        # 📸 لو فيه بوستر
        # -------------------------------------------------

        if photo_id:

            try:

                bot.send_photo(
                    RECOMMEND_CHANNEL_ID,
                    photo_id,
                    caption=safe_markdown(
                        caption_text
                    ),
                    parse_mode="Markdown",
                    reply_markup=markup
                )

                sent_successfully = True

                print(
                    "✅ RECOMMENDATION PHOTO SENT"
                )

            except Exception as photo_error:

                print(
                    "⚠️ SEND PHOTO ERROR:",
                    repr(photo_error)
                )

                # -----------------------------------------
                # نجرب رسالة عادية
                # -----------------------------------------

                try:

                    bot.send_message(
                        RECOMMEND_CHANNEL_ID,
                        safe_markdown(
                            caption_text
                        ),
                        parse_mode="Markdown",
                        reply_markup=markup
                    )

                    sent_successfully = True

                    print(
                        "✅ RECOMMENDATION TEXT SENT"
                    )

                except Exception as text_error:

                    print(
                        "❌ SEND TEXT ERROR:",
                        repr(text_error)
                    )

        # -------------------------------------------------
        # 📝 مفيش صورة
        # -------------------------------------------------

        else:

            try:

                bot.send_message(
                    RECOMMEND_CHANNEL_ID,
                    safe_markdown(
                        caption_text
                    ),
                    parse_mode="Markdown",
                    reply_markup=markup
                )

                sent_successfully = True

                print(
                    "✅ RECOMMENDATION TEXT SENT"
                )

            except Exception as e:

                print(
                    "❌ SEND RECOMMENDATION ERROR:",
                    repr(e)
                )

        # -------------------------------------------------
        # مهم جدًا:
        # نسجل الفيلم فقط لو اتبعت بنجاح
        # -------------------------------------------------

        if not sent_successfully:

            print(
                "❌ RECOMMENDATION WAS NOT SENT"
            )

            print(
                "⚠️ MOVIE WILL NOT BE MARKED AS POSTED"
            )

            return False

        # -------------------------------------------------
        # تسجيل الترشيح
        # -------------------------------------------------

        cursor.execute("""
            INSERT OR IGNORE INTO movie_recommendations
            (
                movie_name,
                posted_at
            )
            VALUES (?, ?)
        """, (
            movie_name,
            datetime.now().isoformat()
        ))

        conn.commit()

        print(
            "✅ MOVIE RECOMMENDED:",
            movie_name
        )

        return True

    except Exception as e:

        print(
            "❌ PUBLISH RECOMMENDATION ERROR:",
            repr(e)
        )

        return False

    finally:
        conn.close()


# =========================================================
# 🔗 RECOMMENDATION START
# =========================================================

def handle_recommendation_start(message, ep_id):

    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:

        # =====================================================
        # 🎬 جلب الفيلم مباشرة بالـ ID
        # =====================================================

        cursor.execute("""
            SELECT file_id, episode_name
            FROM episodes
            WHERE id = ?
        """, (ep_id,))

        episode = cursor.fetchone()

        if not episode:

            bot.send_message(
                message.chat.id,
                "❌ الفيلم غير موجود أو تم حذفه."
            )

            return

        file_id, episode_name = episode

    finally:

        conn.close()

    # =====================================================
    # 🔒 فحص الحظر
    # =====================================================

    is_blocked = user_id in BLOCKED_USERS

    # =====================================================
    # 🎬 إرسال الفيلم مباشرة
    # =====================================================

    try:

        bot.send_video(
            message.chat.id,
            file_id,
            caption=episode_name,
            parse_mode="Markdown",
            protect_content=is_blocked
        )

        print(
            f"🎬 RECOMMENDATION OPENED | "
            f"user={user_id} | ep_id={ep_id}",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ RECOMMENDATION SEND ERROR | "
            f"user={user_id} | ep_id={ep_id} | "
            f"error={repr(e)}",
            flush=True
        )

        bot.send_message(
            message.chat.id,
            "❌ حصل خطأ أثناء إرسال الفيلم، حاول مرة أخرى."
        )

# =========================================================
# ⏰ RECOMMENDATION LOOP
# =========================================================
def recommendation_loop():

    print("🎬 RECOMMENDATION SYSTEM STARTED", flush=True)

    # =====================================================
    # 🎬 أول ترشيح فور تشغيل البوت
    # =====================================================

    try:

        print(
            "🎬 FIRST RECOMMENDATION STARTING...",
            flush=True
        )

        success = publish_movie_recommendation()

        if success:
            print(
                "✅ FIRST RECOMMENDATION POSTED",
                flush=True
            )
        else:
            print(
                "❌ FIRST RECOMMENDATION FAILED",
                flush=True
            )

    except Exception as e:

        print(
            "❌ FIRST RECOMMENDATION ERROR:",
            repr(e),
            flush=True
        )

    # =====================================================
    # 🔁 كل 10 دقائق
    # =====================================================

    while True:

        try:

            print(
                "⏳ RECOMMENDATION: waiting 1 HOURS...",
                flush=True
            )

            # 10 دقائق
            time.sleep(3600)

            print(
                "🎬 1 HOURS PASSED - STARTING RECOMMENDATION...",
                flush=True
            )

            success = publish_movie_recommendation()

            if success:

                print(
                    "✅ RECOMMENDATION POSTED SUCCESSFULLY",
                    flush=True
                )

            else:

                print(
                    "❌ RECOMMENDATION FAILED",
                    flush=True
                )

        except Exception as e:

            print(
                "❌ RECOMMENDATION LOOP ERROR:",
                repr(e),
                flush=True
            )

            print(
                "🔄 RETRYING AFTER 30 SECONDS...",
                flush=True
            )

            time.sleep(30)
def extract_batch_number(text):
    """
    لو الكابشن عبارة عن رقم فقط:
    1
    2
    ١
    ٢
    إلخ
    """

    if not text:
        return None

    text = text.strip()

    # تحويل الأرقام العربية إلى إنجليزية
    arabic_digits = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩",
        "0123456789"
    )

    text = text.translate(arabic_digits)

    # رقم فقط
    if re.fullmatch(r"\d{1,4}", text):
        return int(text)

    return None

def extract_season_episode(text):
    if not text:
        return None

    text = text.strip().upper()

    match = re.search(
        r"S\s*(\d{1,2})\s*E\s*(\d{1,3})",
        text
    )

    if not match:
        return None

    season = int(match.group(1))
    episode = int(match.group(2))

    return season, episode
    
def save_batch_videos(series_name):
    global BATCH_VIDEOS
    global WAITING_FOR_BATCH_NAME

    with BATCH_LOCK:

        videos = BATCH_VIDEOS.copy()

        BATCH_VIDEOS.clear()

        WAITING_FOR_BATCH_NAME = False

    if not videos:
        return

    # ترتيب الفيديوهات
    numeric_videos = all(
        item.get("number") is not None
        for item in videos
    )

    if numeric_videos:

        videos.sort(
            key=lambda x: x["number"]
        )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    saved_count = 0

    for item in videos:

        file_id = item["file_id"]

        quality = item.get("quality") or "HD"

        number = item.get("number")

        season_episode = item.get(
            "season_episode"
        )

        # =================================
        # منع التكرار
        # =================================

        cursor.execute(
            "SELECT id FROM episodes WHERE file_id=?",
            (file_id,)
        )

        if cursor.fetchone():

            print(
                "⚠️ DUPLICATE BATCH FILE:",
                file_id
            )

            continue

        # =================================
        # بناء اسم الحلقة
        # =================================

        if season_episode:

            season, episode = season_episode

            final_title = (
                f"{series_name} "
                f"S{season:02d} E{episode:02d} "
                f"- {quality}"
            )

            notification_episode = (
                f"S{season:02d} E{episode:02d}"
            )

        elif number is not None:

            final_title = (
                f"{series_name} "
                f"حلقة {number} "
                f"- {quality}"
            )

            notification_episode = (
                f"حلقة {number}"
            )

        else:

            final_title = (
                f"{series_name} "
                f"- {quality}"
            )

            notification_episode = None

        linked_caption = (
            f"[{final_title}]"
            f"(https://t.me/cimabotbest)"
        )

        # =================================
        # الحفظ في نفس جدولك
        # =================================

        cursor.execute(
            """
            INSERT INTO episodes
            (
                series_name,
                episode_name,
                file_id,
                quality
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                series_name,
                linked_caption,
                file_id,
                quality
            )
        )

        ep_id = cursor.lastrowid

        saved_count += 1

        # =================================
        # إشعار الحلقة
        # =================================

        if notification_episode:

            try:

                send_new_episode_notification(
                    series_name,
                    notification_episode,
                    quality,
                    ep_id
                )

            except Exception as e:

                print(
                    "NOTIFY ERROR:",
                    e
                )

    conn.commit()
    conn.close()

    # =================================
    # تنظيف الكاش
    # =================================

    for cached_name in list(
        SERIES_CACHE.keys()
    ):

        if normalize_series_name(
            cached_name
        ) == normalize_series_name(
            series_name
        ):

            SERIES_CACHE.pop(
                cached_name,
                None
            )

    # =================================
    # تنظيف السيشنات
    # =================================

    for msg_id, session in list(
        user_sessions.items()
    ):

        if normalize_series_name(
            session.get("series_name", "")
        ) == normalize_series_name(
            series_name
        ):

            user_sessions.pop(
                msg_id,
                None
            )

    # =================================
    # رسالة للأدمن
    # =================================

    bot.send_message(
        ADMIN_ID,
        f"✅ تم تسجيل جميع الفيديوهات\n\n"
        f"🎬 {series_name}\n"
        f"📺 العدد: {saved_count}"
    )
def finish_batch():

    global WAITING_FOR_BATCH_NAME

    with BATCH_LOCK:

        if not BATCH_VIDEOS:
            return

        if WAITING_FOR_BATCH_NAME:
            return

        WAITING_FOR_BATCH_NAME = True

        count = len(BATCH_VIDEOS)

    bot.send_message(
        ADMIN_ID,
        f"🎬 تم اكتشاف دفعة من "
        f"{count} فيديو\n\n"
        f"✏️ اكتب اسم المسلسل الذي تريد "
        f"تسجيل الفيديوهات به:"
    )

def restart_batch_timer():

    global BATCH_TIMER

    if BATCH_TIMER:

        try:
            BATCH_TIMER.cancel()
        except:
            pass

    BATCH_TIMER = threading.Timer(
        BATCH_WAIT_SECONDS,
        finish_batch
    )

    BATCH_TIMER.daemon = True

    BATCH_TIMER.start()

def extract_season_episode_batch(text):
    if not text:
        return None

    text = text.strip().upper()

    match = re.fullmatch(
        r"S\s*(\d{1,2})\s*E\s*(\d{1,3})",
        text
    )

    if not match:
        return None

    season = int(match.group(1))
    episode = int(match.group(2))

    return season, episode

@bot.channel_post_handler(content_types=['video', 'document', 'photo'])
def save_episode_from_channel(message):

    if not message.sender_chat:
        return

    if message.sender_chat.id != CONTENT_CHANNEL_ID:
        return

    if not message.caption:
        return

    raw_caption = message.caption.strip()

    # =========================================
    # 🔥 اكتشاف نظام التسجيل الجماعي
    # =========================================

    batch_number = extract_batch_number(
        raw_caption
    )

    season_episode = extract_season_episode_batch(
        raw_caption
    )

    # =========================================
    # 🔥 لو الفيديو رقم أو S01E01
    # =========================================

    if batch_number is not None or season_episode:

        file_id = None

        if message.video:
            file_id = message.video.file_id

        elif message.document:
            file_id = message.document.file_id

        # الصور لا تدخل Batch
        if not file_id:
            return

        # محاولة استخراج الجودة
        data = parse_caption(raw_caption)

        quality = data.get("quality") or "HD"

        # =========================================
        # 🚫 منع إضافة نفس الملف للـ Batch
        # =========================================

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM episodes WHERE file_id=?",
            (file_id,)
        )

        already_saved = cursor.fetchone()

        conn.close()

        if already_saved:

            print(
                "⚠️ DUPLICATE BATCH FILE"
            )

            return

        # =========================================
        # 💾 إضافة الفيديو للدفعة
        # =========================================

        with BATCH_LOCK:

            BATCH_VIDEOS.append({
                "file_id": file_id,
                "quality": quality,
                "number": batch_number,
                "season_episode": season_episode,
                "caption": raw_caption
            })

            batch_count = len(
                BATCH_VIDEOS
            )

        print(
            f"🔥 BATCH VIDEO ADDED: "
            f"{raw_caption} "
            f"| TOTAL: {batch_count}"
        )

        # =========================================
        # ⏱️ إعادة تشغيل المؤقت
        # =========================================

        restart_batch_timer()

        return

    # =========================================
    # 🧠 استخراج البيانات العادي
    # =========================================

    data = parse_caption(raw_caption)

    # =========================================
    # 🧠 استخراج البيانات
    # =========================================

    series_name_raw = data.get(
        "series_name",
        ""
    )

    clean_title = clean_series_title(
        series_name_raw
    )

    base_series_name = get_base_series_name(
        clean_title
    )

    part_number = extract_part(
        clean_title
    )

    if part_number:

        series_name = (
            f"{base_series_name} "
            f"الموسم {part_number}"
        )

    else:

        series_name = base_series_name

    if not series_name:

        bot.send_message(
            ADMIN_ID,
            "❌ لم أستطع تحديد اسم المسلسل"
        )

        return

    quality = (
        data.get("quality")
        or "HD"
    )

    episode_num = extract_episode_safe(
        raw_caption
    )

    release_year = extract_year(
        raw_caption
    )

    print(
        "SERIES SAVED:",
        series_name
    )

    conn = sqlite3.connect(
        DB_NAME
    )

    cursor = conn.cursor()

    # =========================================
    # 🖼️ حفظ الكابشن والصورة
    # =========================================

    if message.photo:

        photo_file_id = (
            message.photo[-1].file_id
        )

        cursor.execute(
            """
            SELECT id
            FROM series_captions
            WHERE series_name=?
            """,
            (
                series_name,
            )
        )

        exists = cursor.fetchone()

        if not exists:

            cursor.execute(
                """
                INSERT INTO series_captions
                (
                    series_name,
                    caption,
                    photo_file_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    series_name,
                    raw_caption,
                    photo_file_id
                )
            )

            conn.commit()

            print(
                "✅ CAPTION SAVED:",
                series_name
            )

        conn.close()

        return

    # =========================================
    # 📂 FILE ID
    # =========================================

    file_id = None

    if message.video:

        file_id = (
            message.video.file_id
        )

    elif message.document:

        file_id = (
            message.document.file_id
        )

    if not file_id:

        conn.close()

        return

    # =========================================
    # 🚫 منع التكرار
    # =========================================

    cursor.execute(
        "SELECT id FROM episodes WHERE file_id=?",
        (
            file_id,
        )
    )

    if cursor.fetchone():

        conn.close()

        print(
            "⚠️ DUPLICATE FILE"
        )

        return

    # =========================================
    # 🎬 بناء العنوان
    # =========================================

    if episode_num:

        final_title = (
            f"{series_name} "
            f"حلقة {episode_num} "
            f"- {quality}"
        )

    else:

        if release_year:

            final_title = (
                f"{series_name} "
                f"({release_year}) "
                f"- {quality}"
            )

        else:

            final_title = (
                f"{series_name} "
                f"- {quality}"
            )

    linked_caption = (
        f"[{final_title}]"
        f"(https://t.me/cimabotbest)"
    )

    # =========================================
    # 💾 حفظ الحلقة
    # =========================================

    cursor.execute(
        """
        INSERT INTO episodes
        (
            series_name,
            episode_name,
            file_id,
            quality
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            series_name,
            linked_caption,
            file_id,
            quality
        )
    )

    conn.commit()

    ep_id = cursor.lastrowid

    conn.close()

    # =========================================
    # 🔥 تنظيف الكاش
    # =========================================

    for cached_name in list(
        SERIES_CACHE.keys()
    ):

        if (
            normalize_series_name(
                cached_name
            )
            ==
            normalize_series_name(
                series_name
            )
        ):

            SERIES_CACHE.pop(
                cached_name,
                None
            )

    # =========================================
    # 🔥 تنظيف السيشنات
    # =========================================

    for msg_id, session in list(
        user_sessions.items()
    ):

        if (
            normalize_series_name(
                session.get(
                    "series_name",
                    ""
                )
            )
            ==
            normalize_series_name(
                series_name
            )
        ):

            user_sessions.pop(
                msg_id,
                None
            )

    # =========================================
    # 🔔 إشعار الحلقات الجديدة
    # =========================================

    if episode_num:

        try:

            send_new_episode_notification(
                series_name,
                episode_num,
                quality,
                ep_id
            )

        except Exception as e:

            print(
                "NOTIFY ERROR:",
                e
            )

    # =========================================
    # 📊 تجميع الإشعارات
    # =========================================

    key = series_name

    if key not in SAVE_LOGS:

        SAVE_LOGS[key] = {

            "episodes": [],

            "qualities": set(),

            "last": time.time()
        }

    # =========================================
    # حفظ الجودة
    # =========================================

    SAVE_LOGS[key]["qualities"].add(
        quality
    )

    # =========================================
    # حفظ الحلقة
    # =========================================

    if episode_num:

        SAVE_LOGS[key]["episodes"].append(
            f"حلقة {episode_num}"
        )

    else:

        SAVE_LOGS[key]["episodes"].append(
            final_title
        )

    now = time.time()

    # =========================================
    # ⏱️ إرسال ملخص كل 15 ثانية
    # =========================================

    if (
        now
        -
        SAVE_LOGS[key]["last"]
        > 15
    ):

        eps = "\n".join(
            SAVE_LOGS[key]["episodes"][:20]
        )

        qualities_text = " | ".join(
            sorted(
                SAVE_LOGS[key]["qualities"]
            )
        )

        text = (
            f"✅ تم حفظ محتوى جديد\n\n"
            f"🎬 {series_name}\n\n"
            f"📺 الحلقات:\n"
            f"{eps}\n\n"
            f"🎞️ الجودات:\n"
            f"{qualities_text}\n\n"
            f"🔥 العدد: "
            f"{len(SAVE_LOGS[key]['episodes'])}"
        )

        try:

            bot.send_message(
                ADMIN_ID,
                text
            )

        except Exception as e:

            print(
                "ADMIN MSG ERROR:",
                e
            )

        SAVE_LOGS[key] = {

            "episodes": [],

            "qualities": set(),

            "last": now
            }
        send_new_episode_notification(series_name, episode_num, quality, ep_id)
        
def send_new_episode_notification(series_name, episode_num, quality, ep_id):

    if not NOTIFICATIONS_ENABLED:
        return

    # ✅ 720 بس
    if str(quality) not in ["720", "720p"]:
        return 

    # منع التكرار
    notification_key = f"{series_name}_{episode_num}_720"
    current_time = time.time()

    if notification_key in LAST_NOTIFIED:
        if current_time - LAST_NOTIFIED[notification_key] < 60:
            return

    LAST_NOTIFIED[notification_key] = current_time

    # DB
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    caption_data = get_caption_with_fallback(cursor, series_name, media_type="series")

    photo_id, story_text = caption_data if caption_data else (None, "لا يوجد وصف متاح حالياً.")
    conn.close()

    # نوع المحتوى
    is_movie = episode_num is None

    if is_movie:
        header = "🌟 فيلم جديد متاح الآن"
        info_line = f"🎬 الفيلم: {series_name}"
    else:
        header = "🔥 حلقة جديدة نزلت"
        info_line = f"🎬 المسلسل: {series_name}\n🎞 الحلقة: {episode_num}"

    story_block = f"> {story_text}"

    text = f"""
{header}

{info_line}
📺الجودة 720p
📖القصة:
{story_block}
"""

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🎬 مشاهدة 720p",
            url=f"https://t.me/{BOT_USERNAME}?start=episode_{ep_id}",
            style="success"
        )

    )

    try:
        # ✅ 1. البوست الأساسي
        if photo_id:
            msg = bot.send_photo(
                GROUP_ID,
                photo_id,
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        else:
            msg = bot.send_message(
                GROUP_ID,
                text,
                reply_markup=markup,
                parse_mode="Markdown"
            )

        bot.pin_chat_message(GROUP_ID, msg.message_id, disable_notification=True)
    # 🔔 إشعار المفضلة
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM favorites
                WHERE series_name LIKE ?
            """, (f"%{series_name}%",))
            fans = cursor.fetchall()
            conn.close()

            for (fan_id,) in fans:
                try:
                    fan_text = f"""
🔔 *مسلسل من مفضلتك نزلت له حلقة جديدة!*

🎬 *{series_name}*
🎞 الحلقة: {episode_num}
📺 الجودة: 720p
"""
                    fan_markup = types.InlineKeyboardMarkup()
                    fan_markup.add(
                        types.InlineKeyboardButton(
                            "▶️ شاهد الآن",
                            url=f"https://t.me/{BOT_USERNAME}?start=episode_{ep_id}",
                            style="success"
                        )

                    )
                    if photo_id:
                        bot.send_photo(
                            fan_id,
                            photo_id,
                            caption=fan_text,
                            reply_markup=fan_markup,
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(
                            fan_id,
                            fan_text,
                            reply_markup=fan_markup,
                            parse_mode="Markdown",
                        )
                except:
                    pass  # لو المستخدم blocking البوت
        except Exception as e:
            print("FAVORITES NOTIFY ERROR:", e)

        # 🔥 2. البوست الدعائي (جروب تاني)
        PROMO_GROUP_ID =-1003472601279 # ← حط هنا الجروب التاني
        ADMIN_USERNAME = "MohamedOwies"

        promo_text = f"""
🔥🎬 نزلت حلقة جديدة/فيلم جديد 

{info_line}
متاح بكل الجودات 

الاشتراك في البوت ؟
كلم الأدمن 👇
@{ADMIN_USERNAME} 😎🔥
"""

        if photo_id:
            bot.send_photo(
                PROMO_GROUP_ID,
                photo_id,
                caption=promo_text
            )
        else:
            bot.send_message(
                PROMO_GROUP_ID,
                promo_text
            )

    except Exception as e:
        print("Error:", e)
    
@bot.message_handler(
    func=lambda message: (
        message.chat.type in ["group", "supergroup"]
        and not message.text.startswith("/")
    )
)
def choose_type(message):

    query = message.text.strip()

    search_sessions[message.from_user.id] = {
        "query": query,
        "message_id": message.message_id
    }

    # إنشاء اللوحة
    markup = types.InlineKeyboardMarkup(row_width=2)

    btn_movie = types.InlineKeyboardButton(
        text="📺 أفلام",
        callback_data="type_movie",
        style="success"       # 🟢 أخضر
    )

    btn_series = types.InlineKeyboardButton(
        text="🎬 مسلسلات",
        callback_data="type_series",
        style="primary"       # 🔵 أزرق
    )

    markup.add(btn_movie, btn_series)

    text = (
        f"🔍 <b>جاري البحث عن:</b> <code>{query}</code>\n\n"
        f"<b> اختار النوع اللي بتدور عليه:</b> 👇"
    )

    bot.reply_to(
        message,
        text,
        parse_mode="HTML",
        reply_markup=markup
    )
def build_episodes_markup(series_name, episodes, page=0):
    start = page * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    current = episodes[start:end]

    markup = InlineKeyboardMarkup(row_width=1)

    # =========================
    # 📂 زر عرض كل الحلقات
    # =========================
    markup.add(
        InlineKeyboardButton(
            "📂 كل الحلقات",
            callback_data="ep:episodes:0",
            style="success"
        )
    )

    # إرسال الكل: اختيار الجودة ثم تقسيم المتاح إلى مجموعات من 10
    markup.add(
        InlineKeyboardButton(
            "📥 إرسال الكل",
            callback_data="ep:sendall"
        )
    )

    # =========================
    # 🎬 أزرار الحلقات
    # =========================
    for ep_id, ep_name in current:
        clean = ep_name

        # إزالة markdown لو موجود
        if clean.startswith("[") and "](" in clean:
            clean = clean.split("](")[0][1:]

        ep_num = extract_episode(clean)

        text = format_button_text(
            title=clean,
            episode=ep_num,
            quality=extract_quality(clean) or "HD"
        )

        markup.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"ep:select:{ep_id}",
                style="danger"
            
            )
        )

    # =========================
    # ⬅️ ➡️ تنقل الصفحات
    # =========================
    nav = []

    if start > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"ep:page:{page-1}",
                style="danger"
            )
        )

    if end < len(episodes):
        nav.append(
            InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"ep:page:{page+1}",
                style="primary"
            )
        )

    if nav:
        markup.row(*nav)

    return markup


    clean = normalize_series_name(clean.strip())
    return clean, episode

def show_episodes(message):
    query_raw = message.text.strip()
    username = message.from_user.first_name or "صاحبي"
    series_query, wanted_episode = smart_parse_query(query_raw)

    searching_msg = bot.send_message(
        message.chat.id,
        f"⏳ جارٍ البحث يا {username}..."
    ) 
    try:
        bot.delete_message(message.chat.id, searching_msg.message_id)
    except:
        pass

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    matched = []
    detected_series_name = None

    # =========================
    # 🔗 البحث في اللينكات
    # =========================
    cursor.execute("SELECT link_id, series_name FROM links")
    links = cursor.fetchall()

    matched_links = []
    for link_id, s_name in links:
        if word_match(series_query, normalize_series_name(s_name)):
            matched_links.append((link_id, s_name))

    if matched_links:
        try:
            bot.delete_message(message.chat.id, searching_msg.message_id)
        except:
            pass

        markup = InlineKeyboardMarkup()
        for link_id, s_name in matched_links:
            markup.add(
                InlineKeyboardButton(
                    f"📂 {s_name}",
                    url=f"https://t.me/{BOT_USERNAME}?start=series_{link_id}",
                    style="primary"
                )
            )

        bot.send_message(
            message.chat.id,
            "🎬 *هل تقصد المسلسل ده؟*",
            reply_markup=markup,
            parse_mode="Markdown",
        )
        conn.close()
        return

    # =========================
    # 🔵 الكاش
    # =========================
    for cached_series, data in SERIES_CACHE.items():
        if word_match(series_query, cached_series):
            for ep_id, ep_name in data["episodes"]:
                ep_num = extract_episode_safe(ep_name)
                if wanted_episode and ep_num != wanted_episode:
                    continue
                matched.append((ep_id, ep_name))

            detected_series_name = cached_series
            break

    # =========================
    # 🟡 DB
    # =========================
    if not matched:
        cursor.execute("SELECT id, episode_name, series_name FROM episodes")
        rows = cursor.fetchall()
        for ep_id, ep_name, s_name in rows:

            norm_series = normalize_series_name(s_name)

            if not word_match(series_query, norm_series):
                continue

            ep_num = extract_episode_safe(ep_name)
            if wanted_episode and ep_num != wanted_episode:
                continue

            matched.append((ep_id, ep_name))
            detected_series_name = norm_series

        if matched and detected_series_name:
            SERIES_CACHE[detected_series_name] = {
                "episodes": matched,
                "timestamp": time.time()
            }

    try:
        bot.delete_message(message.chat.id, searching_msg.message_id)
    except:
        pass

    if not matched or not detected_series_name:
        bot.send_message(message.chat.id, "ممكن يكون المسلسل ده مش موجود 🥺")
        conn.close()
        return

    # ✅ تسجيل البحث
    try:
        conn2 = sqlite3.connect(DB_NAME)
        cursor2 = conn2.cursor()
        cursor2.execute(
            "INSERT INTO search_history (user_id, query, search_date) VALUES (?, ?, ?)",
            (message.from_user.id, detected_series_name, datetime.now().isoformat())
        )
        conn2.commit()
        conn2.close()
    except:
        pass

    final_series_name = (
        get_series_name_for_caption(detected_series_name)
        or detected_series_name
    )

    # =========================
    # 🖼 الكابشن
    # =========================
    caption_data = get_caption_with_fallback(
        cursor,
        final_series_name,
        media_type="tv"
    )

    conn.close()

    markup = build_episodes_markup(
        final_series_name,
        matched,
        page=0
    )

    photo_id = None
    caption_text = None

    if caption_data:
        photo_id, caption_text = caption_data

    if photo_id and caption_text:
        try:
            msg = bot.send_photo(
                message.chat.id,
                photo_id,
                caption=safe_markdown(caption_text),
                reply_markup=markup,
                parse_mode="Markdown",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            print("SEND PHOTO FAILED:", e)
            msg = bot.send_message(
                message.chat.id,
                safe_markdown(caption_text),
                reply_markup=markup,
                parse_mode="Markdown",
                reply_to_message_id=message.message_id
            )
    elif caption_text:
        msg = bot.send_message(
            message.chat.id,
            safe_markdown(caption_text),
            reply_markup=markup,
            parse_mode="Markdown",
            reply_to_message_id=message.message_id
        )
    else:
        msg = bot.send_message(
            message.chat.id,
            f"🎬 *{safe_markdown(final_series_name)}*",
            reply_markup=markup,
            parse_mode="Markdown",
            reply_to_message_id=message.message_id
        )

    user_sessions[msg.message_id] = {
        "series_name": final_series_name,
        "episodes": matched,
        "page": 0
    }
# =========================
# 🎬 MOVIES PAGINATION
# =========================

MOVIES_PER_PAGE = 10


def build_movies_markup(results, page=0):
    """
    إنشاء أزرار الأفلام مع Pagination
    """

    markup = InlineKeyboardMarkup(row_width=1)

    total_pages = max(
        1,
        (len(results) + MOVIES_PER_PAGE - 1) // MOVIES_PER_PAGE
    )

    # التأكد إن الصفحة صحيحة
    page = max(0, min(page, total_pages - 1))

    start = page * MOVIES_PER_PAGE
    end = start + MOVIES_PER_PAGE

    page_results = results[start:end]

    # أزرار الأفلام
    for ep_id, name, quality in page_results:

        markup.add(
            InlineKeyboardButton(
                f"🎞 {name} — {quality}",
                url=f"https://t.me/{BOT_USERNAME}?start=episode_{ep_id}"
            )
        )

    # أزرار التنقل
    navigation_buttons = []

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"moviepg:{page - 1}"
            )
        )

    if page < total_pages - 1:
        navigation_buttons.append(
            InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"moviepg:{page + 1}"
            )
        )

    if navigation_buttons:
        markup.row(*navigation_buttons)

    # رقم الصفحة
    markup.add(
        InlineKeyboardButton(
            f"📄 صفحة {page + 1} من {total_pages}",
            callback_data="moviepg:noop"
        )
    )

    return markup


def show_movies(message):

    user_id = message.from_user.id

    # =========================
    # 🟢 الجروب → شغال عادي
    # =========================

    if message.chat.type != "private":
        pass

    # =========================
    # 🔴 الخاص
    # =========================

    else:
        if not private_search_mode.get(user_id):
            return

    # 🔥 خروج تلقائي بعد أول استخدام
    private_search_mode.pop(user_id, None)

    # =========================
    # 🔎 البحث
    # =========================

    query_raw = message.text.strip()

    username = message.from_user.first_name or "صاحبي"

    searching_msg = bot.send_message(
        message.chat.id,
        f"⏳ جارٍ البحث يا {username}..."
    )

    try:
        bot.delete_message(
            message.chat.id,
            searching_msg.message_id
        )
    except:
        pass

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, series_name, quality FROM episodes"
    )

    rows = cursor.fetchall()

    results = []
    final_movie_name = None

    for ep_id, series_name, quality in rows:

        if word_match(query_raw, series_name):

            results.append(
                (
                    ep_id,
                    series_name,
                    quality or "HD"
                )
            )

            final_movie_name = series_name

    # =========================
    # ❌ لا توجد نتائج
    # =========================

    if not results or not final_movie_name:

        conn.close()

        bot.send_message(
            message.chat.id,
            "قد يكون الفيلم غير موجود في البوت 🥺"
        )

        return

    # =========================
    # ✅ تسجيل البحث
    # =========================

    try:

        conn2 = sqlite3.connect(DB_NAME)
        cursor2 = conn2.cursor()

        cursor2.execute(
            """
            INSERT INTO search_history
            (user_id, query, search_date, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                message.from_user.id,
                final_movie_name,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            )
        )

        conn2.commit()
        conn2.close()

    except Exception as e:

        print(
            "SEARCH HISTORY ERROR:",
            repr(e)
        )

    # =========================
    # 🖼️ جلب الكابشن
    # =========================

    caption_data = get_caption_with_fallback(
        cursor,
        final_movie_name,
        media_type="movie"
    )

    conn.close()

    photo_id = None
    caption_text = None

    if caption_data:

        photo_id, caption_text = caption_data

    # =========================
    # 📄 إنشاء أول صفحة
    # =========================

    page = 0

    markup = build_movies_markup(
        results,
        page
    )

    sent_message = None

    # =========================
    # 🖼️ إرسال صورة + كابشن
    # =========================

    if photo_id and caption_text:

        try:

            sent_message = bot.send_photo(
                message.chat.id,
                photo_id,
                caption=safe_markdown(caption_text),
                reply_markup=markup,
                parse_mode="Markdown",
                reply_to_message_id=message.message_id
            )

        except Exception as e:

            print(
                "SEND PHOTO FAILED:",
                repr(e)
            )

    # =========================
    # 📝 إرسال كابشن فقط
    # =========================

    if sent_message is None and caption_text:

        sent_message = bot.send_message(
            message.chat.id,
            safe_markdown(caption_text),
            reply_markup=markup,
            parse_mode="Markdown",
            reply_to_message_id=message.message_id
        )

    # =========================
    # 🎬 إرسال اسم الفيلم فقط
    # =========================

    if sent_message is None:

        sent_message = bot.send_message(
            message.chat.id,
            f"🎬 *{safe_markdown(final_movie_name)}*",
            reply_markup=markup,
            parse_mode="Markdown",
            reply_to_message_id=message.message_id
        )

    # =========================
    # 💾 حفظ جلسة الصفحات
    # =========================

    movie_sessions[sent_message.message_id] = {
        "chat_id": message.chat.id,
        "results": results,
        "page": 0
                }

# =========================
# 🎬 MOVIES PAGINATION CALLBACK
# =========================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("moviepg:")
)
def movies_pagination_callback(call):

    try:

        value = call.data.split(":")[1]

        # زر بدون وظيفة
        if value == "noop":

            bot.answer_callback_query(
                call.id
            )

            return

        new_page = int(value)

        message_id = call.message.message_id

        session = movie_sessions.get(message_id)

        if not session:

            bot.answer_callback_query(
                call.id,
                "❌ الصفحة انتهت، اعمل بحث جديد."
            )

            return

        results = session["results"]

        # تحديث الصفحة
        session["page"] = new_page

        markup = build_movies_markup(
            results,
            new_page
        )

        # تعديل الأزرار فقط
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=message_id,
            reply_markup=markup
        )

        bot.answer_callback_query(
            call.id
        )

    except Exception as e:

        print(
            "MOVIES PAGINATION ERROR:",
            repr(e)
        )

        try:

            bot.answer_callback_query(
                call.id,
                "❌ حصل خطأ، حاول تاني."
            )

        except:

            pass

@bot.callback_query_handler(func=lambda call: call.data in ["type_movie", "type_series"])
def handle_type(call):
    user_id = call.from_user.id
    data = search_sessions.get(user_id)

    if not data:
        bot.send_message(call.message.chat.id, "❌ مفيش بحث محفوظ")
        return

    # 🔥 البيانات الجاية من البحث
    query = data.get("query")
    user_message_id = data.get("message_id")

    if not query or not user_message_id:
        bot.send_message(call.message.chat.id, "❌ البيانات غير مكتملة")
        return

    # 🗑 حذف رسالة الاختيار (عادي)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    # 👑 ده بقى message شبه الحقيقي (بـ ID صح)
    real_user_message = SimpleNamespace(
        chat=call.message.chat,
        from_user=call.from_user,
        text=query,
        message_id=user_message_id
    )

    # 🚀 تشغيل البحث
    if call.data == "type_series":
        show_episodes(real_user_message)
    else:
        show_movies(real_user_message)

    # 🧹 تنظيف السيشن
    search_sessions.pop(user_id, None)

def send_episodes_list(chat_id, message_id, series_name, episodes, page=0):
    session = user_sessions.get(message_id)
    if not session:
        return

    seasons = sorted({
        extract_season(name)
        for _, name in episodes
        if extract_season(name) is not None
    })

    session["seasons"] = seasons
    session["all_episodes"] = episodes  # 🔥 نحفظ الأصل

    max_page = (len(episodes) - 1) // EPISODES_PER_PAGE
    page = max(0, min(page, max_page))
    session["page"] = page

    start = page * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    current = episodes[start:end]

    markup = InlineKeyboardMarkup()

    # =====================
    # 🔥 الأزرار الجديدة فوق
    # =====================
    markup.add(
        InlineKeyboardButton("🔄 ارتبلك الحلقات يخويا ", callback_data="ep:sort", style="primary",),
        InlineKeyboardButton("🆕 🔥 الحلقة الجديده يصحبي ", callback_data="ep:latest", style="success")
    ) 

    markup.add(
        InlineKeyboardButton("⚙️ اختر جوده تسمع بيها ", callback_data="ep:qualities", style="success")
    )
    markup.add(
    InlineKeyboardButton(
        "❤️ المفضلة",
        callback_data=f"ep:fav",
        style="danger"
    )
    )
    #markup.add(
    #InlineKeyboardButton("📦 إرسال الكل", callback_data="ep:range")
   # )

    # =====================
    # الأزرار القديمة
    # =====================
    top = []

    if len(seasons) > 1:
        top.append(
            InlineKeyboardButton("🎬 المواسم", callback_data="ep:seasons:0",style="danger"),
        )

    top.append(
        InlineKeyboardButton("📂 الحلقات", callback_data="ep:episodes:0", style="success"),
    )

    markup.add(*top)

    # =====================
    # عرض الحلقات
    # =====================
    for ep_id, ep_name in current:
        clean = ep_name
        if clean.startswith("[") and "](" in clean:
            clean = clean.split("](")[0][1:]

        ep_num = extract_episode(clean)

        text = format_button_text(
            title=clean,
            episode=ep_num,
            quality=extract_quality(clean) or "HD"
        )

        markup.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"ep:num:{ep_num}",
                style="success"
            )
        )

    # تنقل
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("⬅️السابق", callback_data=f"ep:page:{page-1}",style="danger",)),
    if end < len(episodes):
        nav.append(InlineKeyboardButton("➡️التالي", callback_data=f"ep:page:{page+1}",style="success")),

    if nav:
        markup.add(*nav)

    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=markup
    )

# =========================================
# ❤️ FAVORITES
# =========================================

def handle_favorite(call, series_name):

    user_id = call.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM favorites
        WHERE user_id=? AND series_name=?
        """,
        (
            user_id,
            series_name
        )
    )

    exists = cursor.fetchone()

    # =====================
    # ❌ إزالة من المفضلة
    # =====================
    if exists:

        cursor.execute(
            """
            DELETE FROM favorites
            WHERE user_id=? AND series_name=?
            """,
            (
                user_id,
                series_name
            )
        )

        conn.commit()
        conn.close()

        bot.answer_callback_query(
            call.id,
            "💔 تمت الإزالة من المفضلة"
        )

    # =====================
    # ❤️ إضافة للمفضلة
    # =====================
    else:

        cursor.execute(
            """
            INSERT INTO favorites
            (
                user_id,
                series_name
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                series_name
            )
        )

        conn.commit()
        conn.close()

        bot.answer_callback_query(
            call.id,
            "❤️ تمت الإضافة للمفضلة"
        )

def show_sendall_ranges(call, session, series_name, quality):
    """يعرض مجموعات من 10 حلقات للجودة المختارة، بروابط تفتح الخاص."""
    all_eps = session.get("all_episodes", session.get("episodes", []))
    filtered = [
        (ep_id, name) for ep_id, name in all_eps
        if (extract_quality(name) or "HD") == quality
    ]

    if not filtered:
        bot.answer_callback_query(call.id, "❌ مفيش حلقات بالجودة دي", show_alert=True)
        return

    # نخزن رقم حلقة موجود كمرجع قصير نستعيد منه اسم المسلسل في /start
    anchor_id = filtered[0][0]
    markup = InlineKeyboardMarkup(row_width=2)
    total = len(filtered)

    for offset in range(0, total, 10):
        first = offset + 1
        last = min(offset + 10, total)
        payload = f"bulk_{anchor_id}_{quality}_{first}_{last}"

        # Telegram start payload حدّه 64 حرفًا؛ الجودة المعتادة مثل 720p/1080p تناسبه.
        if len(payload) > 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", payload):
            bot.answer_callback_query(
                call.id,
                "❌ اسم الجودة غير مناسب للرابط. ابعتلي اسم الجودة عشان أظبط ترميزها.",
                show_alert=True
            )
            return

        markup.add(InlineKeyboardButton(
            f"📦 {first} - {last}",
            url=f"https://t.me/{BOT_USERNAME}?start={payload}"
        ))

    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="ep:sendall"))
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


# =====================
# 🎯 Callback Handler
# =====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ep:"))
def episodes_callback(call):
    episodes_router(call)


def episodes_router(call):
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    parts = call.data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]
    value = parts[2] if len(parts) > 2 else None

    session = user_sessions.get(msg_id)
    if not session:
        bot.send_message(chat_id, "اعمل بحث جديد كفاية ضغط ع الازرار❌")
        return

    episodes = session["episodes"]
    series_name = session["series_name"]
    page = session.get("page", 0)

    # =====================
    # 📥 إرسال الكل: اختيار الجودة أولاً
    # =====================
    if action == "sendall":
        all_eps = session.get("all_episodes", episodes)
        qualities = sorted({
            extract_quality(name) or "HD"
            for _, name in all_eps
        })

        if not all_eps:
            bot.answer_callback_query(call.id, "❌ مفيش حلقات متاحة", show_alert=True)
            return

        # لو فيه جودة واحدة، اعرض المجموعات مباشرةً
        if len(qualities) == 1:
            quality = qualities[0]
            return show_sendall_ranges(call, session, series_name, quality)

        markup = InlineKeyboardMarkup(row_width=2)
        for quality in qualities:
            markup.add(InlineKeyboardButton(
                f"🎞 {quality}",
                callback_data=f"ep:sendall_quality:{quality}"
            ))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="ep:back"))
        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        return

    if action == "sendall_quality":
        quality = value or "HD"
        return show_sendall_ranges(call, session, series_name, quality)

    # =====================
    # 📂 عرض أرقام الحلقات
    # =====================
    if action == "episodes":
        page = int(value or 0)

        nums = sorted({
            extract_episode(name)
            for _, name in episodes
            if extract_episode(name) is not None
        })

        start = page * EP_NUMBERS_PER_PAGE
        end = start + EP_NUMBERS_PER_PAGE

        markup = InlineKeyboardMarkup(row_width=4)

        for num in nums[start:end]:
            markup.add(
                InlineKeyboardButton(
                    f"الحلقة {num}",
                    callback_data=f"ep:num:{num}",
                    style="danger"
                )
            )

        nav = []
        if start > 0:
            nav.append(
                InlineKeyboardButton("⬅️السابق", callback_data=f"ep:episodes:{page-1}",style="success")
            )
        if end < len(nums):
            nav.append(
                InlineKeyboardButton("➡️التالي", callback_data=f"ep:episodes:{page+1}",style="primary")
            )

        nav.append(
            InlineKeyboardButton("🔙 رجوع", callback_data="ep:back",style="primary")
        )

        markup.add(*nav)

        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        return

    # =====================
    # 🎬 عرض المواسم
    # =====================
    if action == "seasons":
        page = int(value or 0)
        seasons = session.get("seasons", [])

        start = page * 8
        end = start + 8

        markup = InlineKeyboardMarkup(row_width=4)

        for s in seasons[start:end]:
            markup.add(
                InlineKeyboardButton(
                    f"الموسم {s}",
                    callback_data=f"ep:season:{s}",style="danger"
                )
            )

        nav = []
        if start > 0:
            nav.append(
                InlineKeyboardButton("⬅️", callback_data=f"ep:seasons:{page-1}",style="danger")
            )
        if end < len(seasons):
            nav.append(
                InlineKeyboardButton("➡️", callback_data=f"ep:seasons:{page+1}",style="danger")
            )

        nav.append(
            InlineKeyboardButton("🔙 رجوع", callback_data="ep:back",style="danger")
        )

        markup.add(*nav)

        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        return

    # =====================
    # 🎬 اختيار موسم
    # =====================
    if action == "season":
        season = int(value)

        filtered = [
            (eid, name)
            for eid, name in episodes
            if extract_season(name) == season
        ]

        session["episodes"] = filtered
        session["page"] = 0

        send_episodes_list(chat_id, msg_id, series_name, filtered, 0)
        return

    # =====================
    # 🎞 اختيار حلقة → الجودات
    # =====================
    if action == "num":
        ep_num = int(value)

        items = [
            (eid, name)
            for eid, name in episodes
            if extract_episode(name) == ep_num
        ]

        markup = InlineKeyboardMarkup(row_width=2)

        for eid, name in items:
            clean = name
            if clean.startswith("[") and "](" in clean:
                clean = clean.split("](")[0][1:]

            q = extract_quality(clean) or "HD"

            markup.add(
                InlineKeyboardButton(
                    f"🎞 {q}",
                    url=f"https://t.me/{BOT_USERNAME}?start=episode_{eid}",style="success"
                )
            )

        markup.add(
            InlineKeyboardButton("🔙 رجوع", callback_data="ep:episodes:0",style="success")
        )

        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        return

    # =====================
    # ⬅️ ➡️ تنقل الصفحات
    # =====================
    if action == "page":
        page = int(value)
        session["page"] = page

        send_episodes_list(chat_id, msg_id, series_name, episodes, page)
        return

    # =====================
    # 🔙 رجوع
    # =====================
    if action == "back":
        send_episodes_list(
            chat_id,
            msg_id,
            series_name,
            session["episodes"],
            session.get("page", 0)
        )
        return

    # =====================
    # 🔄 ترتيب الحلقات
    # =====================
    if action == "sort":
        eps = sorted(
            session["episodes"],
            key=lambda x: extract_episode(x[1]) or 0
        )

        session["episodes"] = eps
        send_episodes_list(chat_id, msg_id, series_name, eps, 0)
        return

    # =====================
    # 🆕 أحدث حلقة
    # =====================
    if action == "latest":
        all_eps = session["all_episodes"]

        if not all_eps:
            bot.answer_callback_query(call.id, "❌ لا توجد حلقات")
            return

        latest = max(
            all_eps,
            key=lambda x: extract_episode(x[1]) or 0
        )

        send_episodes_list(chat_id, msg_id, series_name, [latest], 0)
        return

    # =====================
    # 🎞 عرض الجودات
    # =====================
    if action == "qualities":
        all_eps = session["all_episodes"]

        qualities = sorted({
            extract_quality(name) or "HD"
            for _, name in all_eps
        })

        markup = InlineKeyboardMarkup()

        for q in qualities:
            markup.add(
                InlineKeyboardButton(
                    f"🎞 {q}",
                    callback_data=f"ep:quality:{q}"
                )
            )

        markup.add(
            InlineKeyboardButton("🔙 رجوع", callback_data="ep:back")
        )

        bot.edit_message_reply_markup(chat_id, msg_id, reply_markup=markup)
        return

    # =====================
    # 🎞 فلترة بالجودة
    # =====================
    if action == "quality":
        q = value
        all_eps = session["all_episodes"]

        filtered = [
            (eid, name)
            for eid, name in all_eps
            if (extract_quality(name) or "HD") == q
        ]

        session["episodes"] = filtered
        send_episodes_list(chat_id, msg_id, series_name, filtered, 0)
        return
        # =====================
    # ❤️ المفضلة
    # =====================
    if action == "fav":

        handle_favorite(
            call,
            series_name
        )

        return
        
        


# =========================================
# 🔥 ADMIN ROUTER
# =========================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_router(call):

    if call.from_user.id != ADMIN_ID:
        return

    action = call.data.replace("admin_", "")

    # =========================================
    # 📢 إذاعة
    # =========================================
    if action == "send":

        start_broadcast(call.message)

    # =========================================
    # 🚫 حظر
    # =========================================
    elif action == "block":

        msg = bot.send_message(
            call.message.chat.id,
            "🚫 ابعت ايدي المستخدم اللي عايز تحظره"
        )

        bot.register_next_step_handler(
            msg,
            block_user
        )

    # =========================================
    # ✅ فك حظر
    # =========================================
    elif action == "unblock":

        msg = bot.send_message(
            call.message.chat.id,
            "✅ ابعت ايدي المستخدم اللي عايز تفك حظره"
        )

        bot.register_next_step_handler(
            msg,
            unblock_user
        )

    # =========================================
    # ➖ حذف اشتراك
    # =========================================
    elif action == "remove":

        msg = bot.send_message(
            call.message.chat.id,
            "➖ ابعت ايدي المستخدم لحذف اشتراكه"
        )

        bot.register_next_step_handler(
            msg,
            remove_subscription
        )

    # =========================================
    # 🧹 مسح الكاش
    # =========================================
    elif action == "clearcache":

        user_sessions.clear()
        series_sessions.clear()
        search_sessions.clear()
        confirm_sessions.clear()

        SERIES_CACHE.clear()
        MOVIES_CACHE.clear()

        USER_TRANSFERS.clear()

        bot.send_message(
            call.message.chat.id,
            "✅ تم مسح الكاش بالكامل"
        )

    # =========================================
    # 🗑 حذف
    # =========================================
    elif action == "delete":

        delete_menu(call.message)

    # =========================================
    # 🔗 إنشاء لينك
    # =========================================
    elif action == "link":

        make_link(call.message)

    # =========================================
    # ❌ حذف لينك
    # =========================================
    elif action == "deletelink":

        msg = bot.send_message(
            call.message.chat.id,
            "❌ ابعت اسم المسلسل لحذف اللينك"
        )

        bot.register_next_step_handler(
            msg,
            delete_link
        )

    # =========================================
    # 🔔 تشغيل الاشعارات
    # =========================================
    elif action == "startnotify":

        start_notify(call.message)

    # =========================================
    # ❌ إيقاف الاشعارات
    # =========================================
    elif action == "stopnotify":

        stop_notify(call.message)

    # =========================================
    # 📊 Stats
    # =========================================
    elif action == "stats":

        show_stats(call.message)

    # =========================================
    # 🏠 الرجوع إلى لوحة القيادة
    # =========================================
    elif action == "back_control":

        bot.answer_callback_query(
            call.id,
            "👑 رجعناك للقيادة"
        )

        try:
            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass

        send_admin_dashboard(
            call.message.chat.id,
            call.from_user.first_name or "قائد"
        )

    # =========================================
    # ❌ Unknown
    # =========================================
    else:

        bot.answer_callback_query(
            call.id,
            "❌ أمر غير معروف"
        )


@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("trend:")
)
def trend_callback(call):

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    # =====================
    # 🔢 INDEX
    # =====================

    idx = int(
        call.data.replace(
            "trend:",
            ""
        )
    )

    queries = trend_sessions.get(
        call.message.chat.id,
        []
    )

    if not queries or idx >= len(queries):

        bot.send_message(
            call.message.chat.id,
            "❌ اعمل /tt تاني"
        )

        return

    query = queries[idx]

    # =====================
    # 🎬 GET MEDIA TYPE
    # =====================

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT media_type
        FROM episodes
        WHERE series_name LIKE ?
        LIMIT 1
        """,
        (f"%{query}%",)
    )

    row = cursor.fetchone()

    conn.close()

    media_type = row[0] if row else "series"

    # =====================
    # 🧠 FAKE MESSAGE
    # =====================

    call.message.text = query
    call.message.from_user = call.from_user

    # =====================
    # 🎥 MOVIE
    # =====================

    if media_type == "movie":

        show_movies(call.message)

    # =====================
    # 📺 SERIES
    # =====================

    else:

        show_episodes(call.message)
        
@bot.message_handler(commands=['start'])
def send_episode_private(message):

    user = message.from_user
    user_id = user.id

    # =====================================================
    # 🔹 قراءة الـ payload
    # =====================================================
    payload = ""

    parts = message.text.split(maxsplit=1)

    if len(parts) > 1:
        payload = parts[1]

    # =====================================================
    # 🧹 حذف رسالة /start
    # =====================================================
    try:
        bot.delete_message(
            message.chat.id,
            message.message_id
        )
    except:
        pass

    # =====================================================
    # ✅ تسجيل المستخدم
    # =====================================================
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (user_id,)
    )

    conn.commit()
    conn.close()

    args = message.text.split()

    # =====================================================
    # 🆕 🔥 تفعيل الاشتراك بالكود
    # =====================================================
    if len(args) > 1 and args[1].startswith("sub_"):

        code = args[1].replace("sub_", "")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT months, used FROM subscription_codes WHERE code=?",
            (code,)
        )

        row = cursor.fetchone()

        if not row:
            conn.close()

            bot.send_message(
                message.chat.id,
                "❌ الكود غير صالح"
            )
            return

        months, used = row

        if used == 1:
            conn.close()

            bot.send_message(
                message.chat.id,
                "❌ الكود تم استخدامه من قبل"
            )
            return

        from datetime import datetime, timedelta

        start = datetime.now()

        end = start + timedelta(
            days=months * 30
        )

        cursor.execute(
            "INSERT OR REPLACE INTO subscriptions VALUES (?, ?, ?)",
            (
                user_id,
                start.isoformat(),
                end.isoformat()
            )
        )

        cursor.execute(
            "UPDATE subscription_codes SET used=1 WHERE code=?",
            (code,)
        )

        conn.commit()
        conn.close()

        bot.send_message(
            message.chat.id,
            f"""🎉 تم تفعيل اشتراكك بنجاح

👤 الاسم: {user.first_name}
🔗 اليوزر: @{user.username if user.username else "لا يوجد"}

📅 البداية: {start.strftime('%Y-%m-%d')}
⏳ النهاية: {end.strftime('%Y-%m-%d')}

💎 المدة: {months} شهر"""
        )

        return

    # =====================================================
    # 🟢 دخول عادي بدون Payload
    # =====================================================
    if len(args) <= 1:

        bot.send_message(
            message.chat.id,
            "Bot series and movie 📺♥️\ncontact programmer @MohamedOwies"
        )

        return

    # =====================================================
    # 🔥 دالة فحص الاشتراك
    # =====================================================
    def is_subscribed(user_id):

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT end_date FROM subscriptions WHERE user_id=?",
            (user_id,)
        )

        row = cursor.fetchone()

        conn.close()

        if not row:
            print(
                f"❌ SUB CHECK | user={user_id} | NO SUBSCRIPTION",
                flush=True
            )
            return False

        end_date = row[0]

        from datetime import datetime

        try:
            end = datetime.fromisoformat(end_date)
            now = datetime.now()

            result = now <= end

            print(
                f"🔐 SUB CHECK | user={user_id} | "
                f"end={end} | now={now} | active={result}",
                flush=True
            )

            return result

        except Exception as e:

            print(
                f"❌ SUB CHECK ERROR | user={user_id} | "
                f"end_date={end_date} | error={repr(e)}",
                flush=True
            )

            return False

    # =====================================================
    # ❌ الاشتراك منتهي
    # =====================================================
    if not is_subscribed(user_id):

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "اضغط لتجديد الاشتراك 🎬",
                url="https://t.me/MohamedOwies",
                style="danger"
            )
        )

        bot.send_message(
            message.chat.id,
            "❌ اشتراكك منتهي\n\nجدد الاشتراك علشان تشوف الحلقات",
            reply_markup=markup
        )

        print(
            f"🚫 ACCESS DENIED | user={user_id} | payload={payload}",
            flush=True
        )

        return

    # =====================================================
    # ✅ من هنا المستخدم مشترك
    # =====================================================

    raw = args[1]

    # =====================================================
    # 🔥 الترشيحات
    # =====================================================
    if raw.startswith("rec_"):

        try:

            ep_id = int(
                raw.replace("rec_", "")
            )

            handle_recommendation_start(
                message,
                ep_id
            )

        except ValueError:

            bot.send_message(
                message.chat.id,
                "رابط الترشيح غير صحيح ❌"
            )

        return

    # =====================================================
    # 🔥 عداد التحميل فقط
    # =====================================================
    if raw.startswith(("episode_", "series_", "bulk_")):

        check_transfer(user)

    # =====================================================
    # هل المستخدم محظور؟
    # =====================================================
    is_blocked = user_id in BLOCKED_USERS

    # =====================================================
    # 📦 إرسال مجموعة حلقات حسب الجودة والنطاق (Deep Link)
    # =====================================================
    if raw.startswith("bulk_"):
        try:
            _, anchor_id_text, requested_quality, first_text, last_text = raw.split("_", 4)
            anchor_id = int(anchor_id_text)
            first = int(first_text)
            last = int(last_text)
            if first < 1 or last < first or last - first > 9:
                raise ValueError("invalid range")
        except (ValueError, TypeError):
            bot.send_message(message.chat.id, "❌ رابط إرسال المجموعة غير صحيح.")
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT series_name FROM episodes WHERE id=?", (anchor_id,))
        anchor_row = cursor.fetchone()
        if not anchor_row:
            conn.close()
            bot.send_message(message.chat.id, "❌ المسلسل أو الحلقة المرجعية لم تعد موجودة.")
            return

        series_name = anchor_row[0]
        cursor.execute(
            "SELECT id, file_id, episode_name, quality FROM episodes WHERE series_name=? ORDER BY id ASC",
            (series_name,)
        )
        db_rows = cursor.fetchall()
        conn.close()

        available = []
        for _, file_id, episode_name, stored_quality in db_rows:
            actual_quality = (extract_quality(episode_name) or stored_quality or "HD").strip()
            # لو العمود موجود لكنه غير متوافق مع الاسم، نعتمد قيمة العمود أولاً كما هي
            if actual_quality == requested_quality:
                available.append((file_id, episode_name))

        if not available:
            bot.send_message(message.chat.id, "❌ مفيش حلقات متاحة بالجودة دي للمسلسل.")
            return

        selected = available[first - 1:last]
        if not selected:
            bot.send_message(message.chat.id, "❌ المجموعة المطلوبة غير موجودة؛ اعمل بحث جديد.")
            return

        bot.send_message(
            message.chat.id,
            f"📥 جاري إرسال {len(selected)} حلقات من *{safe_markdown(series_name)}* بجودة {safe_markdown(requested_quality)}...",
            parse_mode="Markdown"
        )
        sent = 0
        for file_id, episode_name in selected:
            try:
                bot.send_video(
                    message.chat.id,
                    file_id,
                    caption=episode_name,
                    parse_mode="Markdown",
                    protect_content=is_blocked
                )
                sent += 1
                time.sleep(1)
            except Exception as e:
                print(f"BULK SEND ERROR | episode={episode_name!r} | error={e!r}", flush=True)

        bot.send_message(
            message.chat.id,
            f"✅ تم إرسال {sent} من {len(selected)} حلقات. لو عايز مجموعة تانية ارجع لنتيجة البحث واضغط إرسال الكل."
        )
        return

    # =====================================================
    # 🎬 حالة حلقة واحدة
    # =====================================================
    if raw.startswith("episode_"):

        episode_id = raw.replace(
            "episode_",
            ""
        )

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT file_id, episode_name
            FROM episodes
            WHERE id=?
            """,
            (episode_id,)
        )

        episode = cursor.fetchone()

        conn.close()

        if episode:

            file_id, episode_name = episode

            bot.send_video(
                message.chat.id,
                file_id,
                caption=episode_name,
                parse_mode="Markdown",
                protect_content=is_blocked
            )

        else:

            bot.send_message(
                message.chat.id,
                "❌ الحلقة غير موجودة أو تم حذفها."
            )

        return

    # =====================================================
    # 📂 حالة مسلسل كامل
    # =====================================================
    if raw.startswith("series_"):

        link_id = raw.replace(
            "series_",
            ""
        )

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT series_name FROM links WHERE link_id=?",
            (link_id,)
        )

        row = cursor.fetchone()

        if not row:

            conn.close()

            bot.send_message(
                message.chat.id,
                "❌ اللينك غير صالح"
            )

            return

        series_name = row[0]

        cursor.execute(
            """
            SELECT file_id, episode_name
            FROM episodes
            WHERE series_name LIKE ?
            ORDER BY id
            """,
            (f"%{series_name}%",)
        )

        episodes = cursor.fetchall()

        conn.close()

        if not episodes:

            bot.send_message(
                message.chat.id,
                "❌ لا توجد حلقات لهذا المسلسل"
            )

            return

        series_sessions[message.chat.id] = {
            "episodes": episodes,
            "index": 0,
            "blocked": is_blocked
        }

        bot.send_message(
            message.chat.id,
            f"🎬 *{series_name}*\n📂 عدد الحلقات: {len(episodes)}",
            parse_mode="Markdown"
        )

        send_next_batch(
            message.chat.id,
            batch_size=10,
            protect=is_blocked
        )

        return
           
def send_next_batch(chat_id, batch_size=10, protect=False,send_all=False):
    session = series_sessions.get(chat_id)
    if not session:
        return

    episodes = session["episodes"]
    index = session["index"]

    if send_all:
        end = len(episodes)
    else:
        end = index + batch_size

    batch = episodes[index:end]

    for file_id, episode_name in batch:
        bot.send_video(
            chat_id,
            file_id,
            caption=episode_name,
            parse_mode="Markdown",
            protect_content=protect
        )
        time.sleep(1)

    session["index"] = end

    # لسه في حلقات
    if end < len(episodes):
        remaining = len(episodes) - end

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "📥 عايز 10 حلقات كمان",
                callback_data="send_more_10"
            )
        )
        markup.add(
            InlineKeyboardButton(
                f"📦 ابعت باقي المسلسل ({remaining})",
                callback_data="send_all"
            )
        )

        bot.send_message(
            chat_id,
            f"⬇️ لسه فاضل {remaining} حلقة",
            reply_markup=markup
        )
    else:
        bot.send_message(chat_id, "✅ تم إرسال جميع الحلقات")
        series_sessions.pop(chat_id, None)

@bot.callback_query_handler(func=lambda call: call.data == "send_more_10")
def send_more_10_handler(call):
    bot.answer_callback_query(call.id)
    send_next_batch(call.message.chat.id, batch_size=10)

@bot.callback_query_handler(func=lambda call: call.data == "send_all")
def send_all_handler(call):
    bot.answer_callback_query(call.id)
    send_next_batch(call.message.chat.id, send_all=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sendall_"))
def send_all_episodes(call):
    series_name = call.data.split("sendall_")[1]
    user_id = call.from_user.id  # الشخص اللي ضغط الزر

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_id, episode_name FROM episodes WHERE series_name LIKE ? ORDER BY episode_name ASC",
        (f"%{series_name}%",)
    )
    episodes = cursor.fetchall()
    conn.close()

    if not episodes:
        bot.answer_callback_query(call.id, "❌ مفيش حلقات!", show_alert=True)
        return

@bot.message_handler(
    func=lambda message:
        message.from_user.id == ADMIN_ID
        and message.chat.type == "private"
        and WAITING_FOR_BATCH_NAME
)
def receive_batch_series_name(message):

    global WAITING_FOR_BATCH_NAME

    series_name = message.text.strip()

    if not series_name:

        bot.reply_to(
            message,
            "❌ اكتب اسم المسلسل"
        )

        return

    # =========================================
    # 🔥 نبدأ حفظ الدفعة
    # =========================================

    with BATCH_LOCK:

        videos = BATCH_VIDEOS.copy()

        BATCH_VIDEOS.clear()

        WAITING_FOR_BATCH_NAME = False

    if not videos:

        bot.reply_to(
            message,
            "❌ الدفعة فاضية"
        )

        return

    # =========================================
    # 🔢 ترتيب الفيديوهات
    # =========================================

    numeric_videos = all(
        item.get("number") is not None
        for item in videos
    )

    if numeric_videos:

        videos.sort(
            key=lambda x: x["number"]
        )

    else:

        # ترتيب S01E01 حسب الموسم والحلقة
        videos.sort(
            key=lambda x: (
                x["season_episode"][0],
                x["season_episode"][1]
            )
            if x.get("season_episode")
            else (999, 999)
        )

    conn = sqlite3.connect(
        DB_NAME
    )

    cursor = conn.cursor()

    saved_count = 0

    qualities = set()

    saved_episodes = []

    # =========================================
    # 💾 حفظ كل فيديو
    # =========================================

    for item in videos:

        file_id = item["file_id"]

        quality = (
            item.get("quality")
            or "HD"
        )

        number = item.get(
            "number"
        )

        season_episode = item.get(
            "season_episode"
        )

        # =========================================
        # 🚫 منع التكرار
        # =========================================

        cursor.execute(
            "SELECT id FROM episodes WHERE file_id=?",
            (
                file_id,
            )
        )

        if cursor.fetchone():

            print(
                "⚠️ DUPLICATE BATCH FILE"
            )

            continue

        # =========================================
        # 🎬 بناء الاسم
        # =========================================

        if season_episode:

            season, episode = (
                season_episode
            )

            final_title = (
                f"{series_name} "
                f"S{season:02d} "
                f"E{episode:02d} "
                f"- {quality}"
            )

            notification_episode = (
                f"S{season:02d} "
                f"E{episode:02d}"
            )

            saved_episodes.append(
                f"S{season:02d} E{episode:02d}"
            )

        elif number is not None:

            final_title = (
                f"{series_name} "
                f"حلقة {number} "
                f"- {quality}"
            )

            notification_episode = (
                number
            )

            saved_episodes.append(
                f"حلقة {number}"
            )

        else:

            final_title = (
                f"{series_name} "
                f"- {quality}"
            )

            notification_episode = None

            saved_episodes.append(
                final_title
            )

        linked_caption = (
            f"[{final_title}]"
            f"(https://t.me/cimabotbest)"
        )

        # =========================================
        # 💾 الحفظ في جدول episodes
        # =========================================

        cursor.execute(
            """
            INSERT INTO episodes
            (
                series_name,
                episode_name,
                file_id,
                quality
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                series_name,
                linked_caption,
                file_id,
                quality
            )
        )

        ep_id = cursor.lastrowid

        saved_count += 1

        qualities.add(
            quality
        )

        # =========================================
        # 🔔 إشعار الحلقة
        # =========================================

        if notification_episode:

            try:

                send_new_episode_notification(
                    series_name,
                    notification_episode,
                    quality,
                    ep_id
                )

            except Exception as e:

                print(
                    "NOTIFY ERROR:",
                    e
                )

    conn.commit()

    conn.close()

    # =========================================
    # 🔥 تنظيف الكاش
    # =========================================

    for cached_name in list(
        SERIES_CACHE.keys()
    ):

        if (
            normalize_series_name(
                cached_name
            )
            ==
            normalize_series_name(
                series_name
            )
        ):

            SERIES_CACHE.pop(
                cached_name,
                None
            )

    # =========================================
    # 🔥 تنظيف السيشنات
    # =========================================

    for msg_id, session in list(
        user_sessions.items()
    ):

        if (
            normalize_series_name(
                session.get(
                    "series_name",
                    ""
                )
            )
            ==
            normalize_series_name(
                series_name
            )
        ):

            user_sessions.pop(
                msg_id,
                None
            )

    # =========================================
    # 📊 النتيجة
    # =========================================

    eps_text = "\n".join(
        saved_episodes[:30]
    )

    qualities_text = " | ".join(
        sorted(qualities)
    )

    bot.send_message(
        ADMIN_ID,
        f"✅ تم تسجيل جميع الفيديوهات\n\n"
        f"🎬 {series_name}\n\n"
        f"📺 الحلقات:\n"
        f"{eps_text}\n\n"
        f"🎞️ الجودات: {qualities_text}\n\n"
        f"🔥 العدد: {saved_count}"
            )

def make_link(msg):
    bot.send_message(
        msg.chat.id,
        "✔️ ابعت اسم المسلسل اللي عايز تعمل له لينك ثابت:"
    )
    bot.register_next_step_handler(msg, save_series_link)


def save_series_link(msg):
    series_name = msg.text.strip()
    link_id = str(uuid.uuid4())[:8]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO links (series_name, link_id) VALUES (?, ?)",
        (series_name, link_id)
    )
    conn.commit()
    conn.close()

    link = f"https://t.me/{BOT_USERNAME}?start=series_{link_id}"

    bot.send_message(
        msg.chat.id,
        f"✅ تم إنشاء لينك المسلسل بنجاح\n\n"
        f"🎬 {series_name}\n\n"
        f"🔗 اللينك:\n{link}\n\n"
        f"📌 أي حد يضغط عليه هيتحول خاص البوت ويتبعتله كل الحلقات"
    )

@bot.message_handler(commands=['stop_notify'])
def stop_notify(message):
    if message.from_user.id != ADMIN_ID:
        return

    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = False

    bot.reply_to(message, "🔕 تم إيقاف الإشعارات")

@bot.message_handler(commands=['start_notify'])
def start_notify(message):
    if message.from_user.id != ADMIN_ID:
        return

    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = True

    bot.reply_to(message, "🔔 تم تشغيل الإشعارات")

def remove_subscription(message):
    try:
        user_id = message.text.strip()

        if not user_id.isdigit():
            bot.send_message(
                message.chat.id,
                "❌ الـ ID لازم يكون أرقام بس.\n"
                "جرب تاني من زر إلغاء الاشتراك."
            )
            return

        user_id = int(user_id)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # التأكد إن المستخدم عنده اشتراك
        cursor.execute(
            "SELECT end_date FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )

        subscription = cursor.fetchone()

        if not subscription:
            conn.close()

            bot.send_message(
                message.chat.id,
                f"❌ مفيش اشتراك للمستخدم:\n`{user_id}`",
                parse_mode="Markdown"
            )
            return

        # حذف الاشتراك
        cursor.execute(
            "DELETE FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()
        conn.close()

        # رسالة للمستخدم
        try:
            bot.send_message(
                user_id,
                "😏 مبروك يا كنج 😂\n\n"
                "الإدارة قررت إنهاء اشتراكك VIP.\n\n"
                "🔒 اشتراكك اتلغى، والمحتوى المدفوع مش متاح ليك حاليًا.\n\n"
                "لو شايف إن ده حصل بالغلط، راجع الإدارة."
            )
        except Exception as e:
            print(
                f"⚠️ الاشتراك اتلغى لكن مقدرتش أبعت للمستخدم {user_id}: "
                f"{repr(e)}"
            )

        # رسالة للأدمن
        bot.send_message(
            message.chat.id,
            f"✅ تم إلغاء اشتراك المستخدم `{user_id}` بنجاح يا كنج 👑",
            parse_mode="Markdown"
        )

    except Exception as e:
        print("❌ REMOVE SUBSCRIPTION ERROR:", repr(e))

        bot.send_message(
            message.chat.id,
            "❌ حصل خطأ أثناء إلغاء الاشتراك."
        )

@bot.message_handler(commands=['stats'])
def stats_command(message):

    # =========================
    # 🔒 ADMIN ONLY
    # =========================

    if message.from_user.id != ADMIN_ID:

        return

    # =========================
    # 📊 STATS
    # =========================

    text = build_stats_text(DB_NAME)

    bot.send_message(
        message.chat.id,
        text
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith('/favorites'))
def favorites_command(message):
    print(f"FAVORITES CALLED: chat_type={message.chat.type}")
    # باقي الكود

    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT series_name
        FROM favorites
        WHERE user_id=?
        """,
        (user_id,)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        bot.send_message(
            message.chat.id,
            "❌ لا توجد مفضلة"
        )

        return

    text = "❤️ المفضلة الخاصة بك\n\n"

    for row in rows:

        text += f"• {row[0]}\n"

    bot.send_message(
        message.chat.id,
        text
    )

@bot.message_handler(commands=['tt'])
def history_command(message):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT query, COUNT(*) as cnt
        FROM search_history
        GROUP BY query
        ORDER BY cnt DESC
        LIMIT 10
    """)

    top = cursor.fetchall()

    conn.close()

    # =====================
    # 📭 مفيش بيانات
    # =====================

    if not top:

        bot.send_message(
            message.chat.id,
            "📭 مفيش سجل بحث"
        )

        return

    # =====================
    # 🧠 SESSION
    # =====================

    trend_sessions[message.chat.id] = [
        q for q, c in top
    ]

    # =====================
    # 🔥 BUTTONS
    # =====================

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for idx, (query, cnt) in enumerate(top):

        markup.add(

            InlineKeyboardButton(
                f"🔥 {query} ({cnt})",
                callback_data=f"trend:{idx}"
            )

        )

    bot.send_message(
        message.chat.id,
        "🔥 الأكثر بحثاً:",
        reply_markup=markup
    )
    
def get_subscription_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT start_date, end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    start_date, end_date = row
    end_date_dt = datetime.fromisoformat(end_date)
    now = datetime.utcnow()

    delta = end_date_dt - now
    days = delta.days
    hours = delta.seconds // 3600

    return {
        "start": start_date,
        "end": end_date,
        "days_left": days,
        "hours_left": hours
    }

@bot.message_handler(commands=['edit_sub'])
def edit_sub_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    msg = bot.send_message(
        message.chat.id,
        "🆔 ابعت ايدي المستخدم"
    )

    bot.register_next_step_handler(msg, get_edit_sub_user)


def get_edit_sub_user(message):

    try:
        user_id = int(message.text.strip())

        msg = bot.send_message(
            message.chat.id,
            "⏳ ابعت المدة:\n\n"
            "➕ إضافة:\n"
            "1h = ساعة\n"
            "1d = يوم\n"
            "1w = أسبوع\n"
            "2w = أسبوعين\n"
            "1m = شهر\n\n"
            "➖ خصم:\n"
            "-1h\n"
            "-1d\n"
            "-1w\n"
            "-1m"
        )

        bot.register_next_step_handler(
            msg,
            process_edit_sub,
            user_id
        )

    except:
        bot.reply_to(message, "❌ ايدي غير صحيح")


def process_edit_sub(message, user_id):

    try:

        value = message.text.strip().lower()

        mode = "add"

        if value.startswith("-"):
            mode = "remove"
            value = value[1:]

        days = 0
        hours = 0

        if value.endswith("h"):
            hours = int(value[:-1])

        elif value.endswith("d"):
            days = int(value[:-1])

        elif value.endswith("w"):
            days = int(value[:-1]) * 7

        elif value.endswith("m"):
            days = int(value[:-1]) * 30

        else:
            bot.reply_to(
                message,
                "❌ صيغة غير صحيحة\n\n"
                "أمثلة:\n"
                "1h = ساعة\n"
                "1d = يوم\n"
                "1w = أسبوع\n"
                "1m = شهر\n\n"
                "-1d = خصم يوم"
            )
            return

        new_date = update_subscription(
            user_id,
            days=days,
            hours=hours,
            mode=mode
        )

        info = get_subscription_info(user_id)

        # =========================
        # إشعار المستخدم
        # =========================

        try:

            if mode == "add":

                if hours:
                    notify_text = f"🎉 تم إضافة {hours} ساعة لاشتراكك بنجاح"

                elif days == 7:
                    notify_text = "🎉 تم إضافة أسبوع لاشتراكك بنجاح"

                elif days == 14:
                    notify_text = "🎉 تم إضافة أسبوعين لاشتراكك بنجاح"

                elif days == 30:
                    notify_text = "🎉 تم إضافة شهر لاشتراكك بنجاح"

                else:
                    notify_text = f"🎉 تم إضافة {days} يوم لاشتراكك بنجاح"

            else:

                if hours:
                    notify_text = f"⚠️ تم خصم {hours} ساعة من اشتراكك"

                elif days == 7:
                    notify_text = "⚠️ تم خصم أسبوع من اشتراكك"

                elif days == 14:
                    notify_text = "⚠️ تم خصم أسبوعين من اشتراكك"

                elif days == 30:
                    notify_text = "⚠️ تم خصم شهر من اشتراكك"

                else:
                    notify_text = f"⚠️ تم خصم {days} يوم من اشتراكك"

            markup = InlineKeyboardMarkup()

            markup.add(
                InlineKeyboardButton(
                    "📞 التواصل مع الدعم",
                    url="https://t.me/MohamedOwies"
                )
            )

            bot.send_message(
                user_id,
                f"{notify_text}\n\n"
                f"📅 تاريخ انتهاء الاشتراك:\n"
                f"{new_date.strftime('%Y-%m-%d %H:%M')}",
                reply_markup=markup
            )

        except Exception as e:
            print("Notify User Error:", e)

        # =========================
        # رسالة الأدمن
        # =========================

        bot.send_message(
            message.chat.id,
            f"✅ تم تعديل الاشتراك\n\n"
            f"👤 ID : {user_id}\n"
            f"📅 ينتهي في : {new_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ المتبقي : {info['days_left']} يوم و {info['hours_left']} ساعة"
        )

    except Exception as e:
        print("EDIT SUB ERROR:", e)

        bot.reply_to(
            message,
            "❌ حصل خطأ أثناء التعديل"
            )


def get_subscription_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT start_date, end_date FROM subscriptions WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    start_date, end_date = row

    end_date_dt = datetime.fromisoformat(end_date)
    now = datetime.now()

    delta = end_date_dt - now

    if delta.total_seconds() < 0:
        days = 0
        hours = 0
    else:
        days = delta.days
        hours = delta.seconds // 3600

    return {
        "start": start_date,
        "end": end_date,
        "days_left": days,
        "hours_left": hours
    }


def update_subscription(user_id, days=0, hours=0, mode="add"):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT end_date FROM subscriptions WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    now = datetime.now()

    if row:

        end_date = datetime.fromisoformat(row[0])

        if end_date < now:
            end_date = now

    else:

        end_date = now

        cursor.execute(
            """
            INSERT OR IGNORE INTO subscriptions
            (user_id, start_date, end_date)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S")
            )
        )

    delta = timedelta(
        days=days,
        hours=hours
    )

    if mode == "add":
        new_end = end_date + delta
    else:
        new_end = end_date - delta

        if new_end < now:
            new_end = now

    cursor.execute(
        """
        UPDATE subscriptions
        SET end_date = ?
        WHERE user_id = ?
        """,
        (
            new_end.strftime("%Y-%m-%d %H:%M:%S"),
            user_id
        )
    )

    conn.commit()
    conn.close()

    return new_end

def delete_link(message):
    if message.chat.id != ADMIN_ID:
        return

    query = " ".join(message.text.split()[1:]).strip()
    if not query:
        bot.reply_to(message, "❌ اكتب اسم المسلسل بعد الأمر")
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, series_name FROM links")
    rows = cur.fetchall()
    conn.close()

    matched = []
    for link_id, series_name in rows:
        if word_match(query, series_name):
            matched.append((link_id, series_name))

    if not matched:
        bot.reply_to(message, "❌ مفيش أي لينك مطابق للاسم ده")
        return

    # ✅ لينك واحد → حذف مباشر
    if len(matched) == 1:
        link_id, series_name = matched[0]

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM links WHERE id=?", (link_id,))
        conn.commit()
        conn.close()

        bot.reply_to(
            message,
            f"✅ تم حذف لينك المسلسل:\n🎬 {series_name}"
        )
        return

    # 🟡 أكتر من لينك → اختيار
    markup = InlineKeyboardMarkup()
    for link_id, series_name in matched:
        markup.add(
            InlineKeyboardButton(
                f"🗑 حذف: {series_name}",
                callback_data=f"confirm_delete_link_{link_id}"
            )
        )

    bot.reply_to(
        message,
        "⚠️ فيه أكتر من لينك للمسلسل ده\nاختار أنهي واحد يتحذف:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_link_"))
def confirm_delete_link(call):
    if call.message.chat.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ غير مسموح")
        return

    link_id = call.data.split("confirm_delete_link_")[1]

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT series_name FROM links WHERE id=?", (link_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        bot.answer_callback_query(call.id, "❌ اللينك غير موجود")
        return

    series_name = row[0]

    cur.execute("DELETE FROM links WHERE id=?", (link_id,))
    conn.commit()
    conn.close()

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    bot.send_message(
        call.message.chat.id,
        f"✅ تم حذف لينك المسلسل:\n🎬 {series_name}"
    )

    bot.answer_callback_query(call.id)
    

def delete_menu(message):
    if message.chat.id != ADMIN_ID:
        return

    msg = bot.send_message(
        ADMIN_ID,
        "🗑 اختر ما تريد حذفه:\n\n"
        "1️⃣ اكتب: حلقة\n"
        "2️⃣ اكتب: مسلسل"
    )
    bot.register_next_step_handler(msg, delete_choice)

def delete_choice(message):
    if message.chat.id != ADMIN_ID:
        return

    choice = message.text.strip()

    if choice == "حلقة":
        msg = bot.send_message(ADMIN_ID, "🔹 أرسل اسم الحلقة بالظبط:")
        bot.register_next_step_handler(msg, delete_episode_by_name)

    elif choice == "مسلسل":
        msg = bot.send_message(ADMIN_ID, "🔹 أرسل اسم المسلسل:")
        bot.register_next_step_handler(msg, delete_series_by_name)

    else:
        bot.send_message(ADMIN_ID, "❌ اختيار غير صحيح.")

def delete_episode_by_name(message):
    if message.chat.id != ADMIN_ID:
        return

    query = message.text.strip()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM episodes WHERE episode_name LIKE ?",
        (f"%{query}%",)
    )

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted:
        bot.send_message(
            ADMIN_ID,
            f"✅ تم حذف {deleted} حلقة تطابق:\n{query}"
        )
    else:
        bot.send_message(
            ADMIN_ID,
            "❌ الحلقة غير موجودة."
        )
def delete_series_by_name(message):
    if message.chat.id != ADMIN_ID:
        return

    raw = message.text.strip()
    search = normalize_series_name(raw)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT series_name FROM episodes"
    )
    rows = cursor.fetchall()

    matched_series = set()

    for (s_name,) in rows:
        if normalize_series_name(s_name).find(search) != -1:
            matched_series.add(s_name)

    if not matched_series:
        bot.send_message(ADMIN_ID, "❌ المسلسل غير موجود.")
        conn.close()
        return

    total_deleted = 0
    for s in matched_series:
        cursor.execute(
            "DELETE FROM episodes WHERE series_name = ?",
            (s,)
        )
        total_deleted += cursor.rowcount

    conn.commit()
    conn.close()

    bot.send_message(
        ADMIN_ID,
        f"✅ تم حذف المسلسل بنجاح\n"
        f"🎬 الاسم: {raw}\n"
        f"🗑 عدد الحلقات: {total_deleted}"
    )


def clear_cache(message):
    if message.from_user.id != ADMIN_ID:
        return

    user_sessions.clear()
    series_sessions.clear()
    search_sessions.clear()
    confirm_sessions.clear()

    SERIES_CACHE.clear()
    MOVIES_CACHE.clear()

    USER_TRANSFERS.clear()

    bot.send_message(message.chat.id, "✅ تم مسح الكاش بالكامل من الرام")

def generate_code(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@bot.message_handler(commands=['renew'])
def create_sub_link(message):

    # 🔐 حماية للأدمن
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ انت مش الادمن")
        return

    try:
        text = message.text.split()[1]

        # 🧠 تحويل الكلام لعدد شهور
        if text == "سنه" or text == "سنة":
            months = 12
        else:
            months = int(text)

    except:
        bot.reply_to(message, "❌ استخدم كده:\nشهر 1\nشهر 3\nشهر 6\nشهر سنة")
        return

    # 🎲 توليد كود
    code = generate_code()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO subscription_codes (code, months, used) VALUES (?, ?, 0)",
        (code, months)
    )

    conn.commit()
    conn.close()

    # 🔗 اللينك
    link = f"https://t.me/{BOT_USERNAME}?start=sub_{code}"

    bot.reply_to(
        message,
        f"""🔥 تم إنشاء رابط اشتراك

📦 المدة: {months} شهر
🔗 اللينك:
{link}

⚠️ يستخدم مرة واحدة فقط"""
    )

@bot.message_handler(commands=['myplan'])
def myplan_command(message):

    user = message.from_user
    user_id = user.id

    # 🇪🇬 توقيت مصر
    egypt_tz = ZoneInfo("Africa/Cairo")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT start_date, end_date FROM subscriptions WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()
    conn.close()

    # ❌ مفيش اشتراك
    if not row:
        bot.send_message(
            message.chat.id,
            "❌ لا يوجد لديك اشتراك مفعل"
        )
        return

    # تحويل التواريخ الموجودة في قاعدة البيانات
    start_date = datetime.fromisoformat(row[0])
    end_date = datetime.fromisoformat(row[1])

    # لو التواريخ في قاعدة البيانات بدون timezone
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=egypt_tz)

    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=egypt_tz)

    # 🇪🇬 الوقت الحالي بتوقيت مصر
    now = datetime.now(egypt_tz)

    remaining = end_date - now

    # ❌ منتهي
    if remaining.total_seconds() <= 0:

        status = "❌ منتهي"
        remaining_text = "0 يوم / 0 ساعة / 0 دقيقة / 0 ثانية"

    else:

        status = "✅ فعال"

        total_seconds = int(remaining.total_seconds())

        days = total_seconds // 86400
        total_seconds %= 86400

        hours = total_seconds // 3600
        total_seconds %= 3600

        minutes = total_seconds // 60
        seconds = total_seconds % 60

        remaining_text = (
            f"{days} يوم / "
            f"{hours} ساعة / "
            f"{minutes} دقيقة / "
            f"{seconds} ثانية"
        )

    # 📅 التاريخ والوقت بالكامل
    start_text = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_text = end_date.strftime("%Y-%m-%d %H:%M:%S")
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")

    text = f"""
💎 *بيانات اشتراكك*

👤 الاسم: {user.first_name}

🔗 اليوزر: @{user.username if user.username else "لا يوجد"}

🆔 ID: `{user_id}`

━━━━━━━━━━━━━━

🕐 *الوقت الحالي*
🇪🇬 {now_text}

📅 *بداية الاشتراك*
🇪🇬 {start_text}

⏳ *نهاية الاشتراك*
🇪🇬 {end_text}

━━━━━━━━━━━━━━

📊 الحالة: {status}

⌛ *المتبقي:*
{remaining_text}

🇪🇬 توقيت القاهرة - مصر
"""

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown"
    )

# =========================================
# 👑 لوحة التحكم الرئيسية
# =========================================
@bot.message_handler(commands=['control'])
def admin_control(message):
    if message.from_user.id != ADMIN_ID:
        return

    send_admin_dashboard(
        message.chat.id,
        message.from_user.first_name or "قائد"
    )
    
def send_admin_dashboard(chat_id, admin_name="قائد"):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 👤 المستخدمين
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]

    # 🎞 الفيديوهات
    cursor.execute("SELECT COUNT(*) FROM episodes")
    episodes_count = cursor.fetchone()[0]

    # 🔗 اللينكات
    cursor.execute("SELECT COUNT(*) FROM links")
    links_count = cursor.fetchone()[0]

    # 💎 الاشتراكات
    cursor.execute("""
        SELECT user_id, end_date
        FROM subscriptions
    """)
    rows = cursor.fetchall()

    conn.close()

    egypt_tz = ZoneInfo("Africa/Cairo")
    now = datetime.now(egypt_tz)

    active = 0
    expired = 0

    for user_id, end in rows:

        try:
            end_date = datetime.fromisoformat(end)

            if end_date.tzinfo is None:
                end_date = end_date.replace(
                    tzinfo=egypt_tz
                )
            else:
                end_date = end_date.astimezone(
                    egypt_tz
                )

            if end_date > now:
                active += 1
            else:
                expired += 1

        except:
            pass

    text = f"""
╔══════════════════════════╗
        👑 <b>لوحة القيادة</b>
╚══════════════════════════╝

🔥 أهلاً بيك يا قائد <b>{admin_name}</b>

━━━━━━━━━━━━━━━━━━━━

📊 <b>إحصائيات البوت</b>

👤 المستخدمين
└─ <code>{users_count}</code> مستخدم

🎞 المحتوى
└─ <code>{episodes_count}</code> فيديو

🔗 اللينكات
└─ <code>{links_count}</code> لينك

━━━━━━━━━━━━━━━━━━━━

💎 <b>الاشتراكات</b>

✅ النشطين
└─ <code>{active}</code> مشترك

❌ المنتهيين
└─ <code>{expired}</code> مشترك

━━━━━━━━━━━━━━━━━━━━

🇪🇬 <b>توقيت القاهرة</b>

📅 <code>{now.strftime("%Y-%m-%d")}</code>
🕐 <code>{now.strftime("%H:%M:%S")}</code>

━━━━━━━━━━━━━━━━━━━━
        ⚡ <b>مركز التحكم الرئيسي</b>
━━━━━━━━━━━━━━━━━━━━
"""

    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "📢 إذاعة",
            callback_data="admin_send",
            style="danger"
        ),
        types.InlineKeyboardButton(
            "🗑 حذف",
            callback_data="admin_delete",
            style="success"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🚫 Block",
            callback_data="admin_block",
            style="danger"
        ),
        types.InlineKeyboardButton(
            "✅ Unblock",
            callback_data="admin_unblock",
            style="success"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "➖ حذف اشتراك",
            callback_data="admin_remove",
            style="primary"
        ),
        types.InlineKeyboardButton(
            "🧹 مسح الكاش",
            callback_data="admin_clearcache",
            style="success"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔗 إنشاء لينك",
            callback_data="admin_link",
            style="primary"
        ),
        types.InlineKeyboardButton(
            "❌ حذف لينك",
            callback_data="admin_deletelink",
            style="danger"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✅ المشتركين النشطين",
            callback_data="show_active_0",
            style="success"
        ),
        types.InlineKeyboardButton(
            "❌ المنتهيين",
            callback_data="show_expired_0",
            style="danger"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "👥 إدارة المستخدمين",
            callback_data="admin_users",
            style="primary"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )
    
PAGE_SIZE = 10
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("show_active_")
)
def show_active(call):

    # 🔐 الأدمن فقط
    if call.from_user.id != ADMIN_ID:
        return

    page = int(call.data.split("_")[-1])

    # 🇪🇬 توقيت مصر
    egypt_tz = ZoneInfo("Africa/Cairo")
    now = datetime.now(egypt_tz)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, end_date
        FROM subscriptions
        ORDER BY end_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    active_users = []

    for user_id, end_date in rows:

        try:
            end_dt = datetime.fromisoformat(end_date)

            # لو التاريخ المخزن بدون timezone
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=egypt_tz)
            else:
                end_dt = end_dt.astimezone(egypt_tz)

            if end_dt > now:
                active_users.append(
                    (user_id, end_dt)
                )

        except Exception as e:
            print("ACTIVE DATE ERROR:", e)

    # 📄 تقسيم الصفحات
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE

    users_page = active_users[start:end]

    total_pages = max(
        1,
        (len(active_users) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    current_page = page + 1

    # 👑 عنوان الصفحة
    text = (
        "╔══════════════════════════╗\n"
        "        👑 <b>المشتركين النشطين</b>\n"
        "╚══════════════════════════╝\n\n"

        f"💎 <b>إجمالي المشتركين:</b> "
        f"<code>{len(active_users)}</code>\n"

        f"📄 <b>الصفحة:</b> "
        f"<code>{current_page} / {total_pages}</code>\n"

        f"🇪🇬 <b>توقيت القاهرة:</b> "
        f"<code>{now.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # 👤 المستخدمين
    for index, (user_id, end_dt) in enumerate(users_page, start=start + 1):

        try:
            user = bot.get_chat(user_id)

            name = user.first_name or "غير معروف"

            username = (
                f"@{user.username}"
                if user.username
                else "لا يوجد"
            )

        except Exception:
            name = "غير معروف"
            username = "غير معروف"

        # ⏳ حساب الوقت المتبقي بدقة
        remaining = end_dt - now

        total_seconds = max(
            0,
            int(remaining.total_seconds())
        )

        days = total_seconds // 86400
        total_seconds %= 86400

        hours = total_seconds // 3600
        total_seconds %= 3600

        minutes = total_seconds // 60
        seconds = total_seconds % 60

        end_text = end_dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        text += (
            f"👤 <b>#{index} {name}</b>\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📛 {username}\n\n"

            f"⏳ <b>المتبقي:</b>\n"
            f"   🗓 {days} يوم  "
            f"🕐 {hours} ساعة\n"
            f"   ⏱ {minutes} دقيقة  "
            f"⚡ {seconds} ثانية\n\n"

            f"📅 <b>ينتهي في:</b>\n"
            f"🇪🇬 <code>{end_text}</code>\n"

            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    # لو الصفحة فاضية
    if not users_page:
        text += (
            "📭 <b>لا يوجد مشتركين في هذه الصفحة.</b>\n\n"
        )

    # 🎛 الأزرار
    markup = types.InlineKeyboardMarkup(row_width=2)

    navigation_buttons = []

    if page > 0:
        navigation_buttons.append(
            types.InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"show_active_{page - 1}",
                style="primary"
            )
        )

    if end < len(active_users):
        navigation_buttons.append(
            types.InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"show_active_{page + 1}",
                style="primary"
            )
        )

    if navigation_buttons:
        markup.row(*navigation_buttons)

    # 🏠 رجوع للوحة القيادة
    markup.add(
        types.InlineKeyboardButton(
            "🏠 لوحة القيادة",
            callback_data="admin_back_control",
            style="success"
        )
    )

    # 🔄 تحديث
    markup.add(
        types.InlineKeyboardButton(
            "🔄 تحديث القائمة",
            callback_data=f"show_active_{page}",
            style="primary"
        )
    )

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:
        print("SHOW ACTIVE EDIT ERROR:", e)

@bot.callback_query_handler(
    func=lambda call: call.data == "admin_back_control"
)
def admin_back_control(call):

    if call.from_user.id != ADMIN_ID:
        return

    bot.answer_callback_query(
        call.id,
        "👑 رجعناك للقيادة"
    )

    try:
        bot.delete_message(
            call.message.chat.id,
            call.message.message_id
        )
    except:
        pass

    send_admin_dashboard(
        call.message.chat.id,
        call.from_user.first_name or "قائد"
    )

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("show_expired_")
)

def show_expired(call):

    # 🔐 الأدمن فقط
    if call.from_user.id != ADMIN_ID:
        return

    page = int(call.data.split("_")[-1])

    # 🇪🇬 توقيت مصر
    egypt_tz = ZoneInfo("Africa/Cairo")
    now = datetime.now(egypt_tz)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, end_date
        FROM subscriptions
        ORDER BY end_date DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    expired_users = []

    for user_id, end_date in rows:

        try:

            end_dt = datetime.fromisoformat(end_date)

            # لو التاريخ المخزن بدون timezone
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(
                    tzinfo=egypt_tz
                )
            else:
                end_dt = end_dt.astimezone(
                    egypt_tz
                )

            if end_dt <= now:

                expired_users.append(
                    (user_id, end_dt)
                )

        except Exception as e:
            print("EXPIRED DATE ERROR:", e)

    # 📄 Pagination
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE

    users_page = expired_users[start:end]

    total_pages = max(
        1,
        (len(expired_users) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    current_page = page + 1

    # 👑 عنوان الصفحة
    text = (
        "╔══════════════════════════╗\n"
        "       ❌ <b>الاشتراكات المنتهية</b>\n"
        "╚══════════════════════════╝\n\n"

        f"📊 <b>إجمالي المنتهيين:</b> "
        f"<code>{len(expired_users)}</code>\n"

        f"📄 <b>الصفحة:</b> "
        f"<code>{current_page} / {total_pages}</code>\n"

        f"🇪🇬 <b>الوقت الحالي:</b>\n"
        f"<code>{now.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"

        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # 👤 عرض المستخدمين
    for index, (user_id, end_dt) in enumerate(
        users_page,
        start=start + 1
    ):

        try:

            user = bot.get_chat(user_id)

            name = (
                user.first_name
                or "غير معروف"
            )

            username = (
                f"@{user.username}"
                if user.username
                else "لا يوجد"
            )

        except Exception:

            name = "غير معروف"
            username = "غير معروف"

        # 📅 وقت انتهاء الاشتراك
        end_text = end_dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        text += (
            f"👤 <b>#{index} {name}</b>\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📛 {username}\n\n"

            f"🔴 <b>انتهى الاشتراك في:</b>\n"
            f"🇪🇬 <code>{end_text}</code>\n"

            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    # 📭 مفيش مستخدمين
    if not users_page:

        text += (
            "📭 <b>لا توجد اشتراكات منتهية هنا.</b>\n\n"
        )

    # 🎛 لوحة الأزرار
    markup = types.InlineKeyboardMarkup(row_width=2)

    navigation_buttons = []

    # ⬅️ السابق
    if page > 0:

        navigation_buttons.append(
            types.InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"show_expired_{page - 1}",
                style="primary"
            )
        )

    # ➡️ التالي
    if end < len(expired_users):

        navigation_buttons.append(
            types.InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"show_expired_{page + 1}",
                style="primary"
            )
        )

    if navigation_buttons:
        markup.row(*navigation_buttons)

    # 🏠 لوحة القيادة
    markup.add(
        types.InlineKeyboardButton(
            "🏠 لوحة القيادة",
            callback_data="admin_back_control",
            style="success"
        )
    )

    # 🔄 تحديث
    markup.add(
        types.InlineKeyboardButton(
            "🔄 تحديث القائمة",
            callback_data=f"show_expired_{page}",
            style="primary"
        )
    )

    # ✏️ تعديل نفس الرسالة
    try:

        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:

        print(
            "SHOW EXPIRED EDIT ERROR:",
            e
        )
def unblock_user(message):

    try:
        user_id = int(message.text)

        BLOCKED_USERS.discard(user_id)

        bot.send_message(
            message.chat.id,
            f"✅ تم فك الحظر عن {user_id}"
        )

    except:
        bot.send_message(
            message.chat.id,
            "❌ ايدي غير صحيح"
        )


# =========================================
# 🧹 تنظيف الأسماء
# =========================================

def clean_name(text):

    text = text.lower()

    text = re.sub(
        r'[^a-zA-Z0-9\u0600-\u06FF ]',
        '',
        text
    )

    text = " ".join(text.split())

    return text.strip()


# =========================================
# 🤖 تشغيل البحث الحقيقي من AI
# =========================================

def ai_show_movie(chat_id, title, reply_to=None):

    class FakeUser:
        id = 0
        first_name = "سهرة"

    class FakeChat:
        type = "private"
        id = chat_id

    class FakeMessage:
        text = title
        chat = FakeChat()
        from_user = FakeUser()
        message_id = reply_to or 0

    # ✅ تفعيل وضع البحث الخاص
    private_search_mode[0] = True

    # 🚀 تشغيل فانكشن البحث الأصلية
    show_movies(FakeMessage())


# =========================================
# 🤖 AI CHAT
# =========================================

@bot.message_handler(func=lambda message: True, content_types=['text'])
def private_ai_chat(message):

    # ❌ تجاهل الجروبات والأوامر
    if message.chat.type != "private":
        return

    if message.text.startswith('/'):
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    # =========================================
    # 👑 VIP CHECK
    # =========================================

    is_vip = False

    try:

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )

        conn.commit()

        cursor.execute(
            "SELECT 1 FROM subscriptions WHERE user_id=?",
            (user_id,)
        )

        if cursor.fetchone():
            is_vip = True

        conn.close()

    except Exception as e:

        print("DB ERROR:", e)

    # ❌ مش مشترك
    if not is_vip:

        bot.reply_to(
            message,
            "عذراً يا بطل 🌟\n"
            "ميزة الذكاء الاصطناعي والترشيحات للـ VIP فقط 👑"
        )

        return

    # =========================================
    # 🔍 تجاهل لو في وضع بحث
    # =========================================

    if user_id in search_sessions:
        return

    if private_search_mode.get(user_id):
        return

    # =========================================
    # ⌨️ Typing
    # =========================================

    try:
        bot.send_chat_action(message.chat.id, 'typing')
    except:
        pass

    # =========================================
    # 🚀 AI SYSTEM
    # =========================================

    try:

        from datetime import datetime

        current_date = datetime.now().strftime("%Y-%m-%d")

        # =========================================
        # 🔥 البرومبت
        # =========================================
        full_prompt = f"""
التاريخ الحالي: {current_date}

اسمك: سهرة 🎬

شخصيتك:
- ولد مصري روش وخفيف الدم.
- خبير أفلام ومسلسلات.
- بتتكلم بالعامية المصرية.
- ردودك قصيرة وطبيعية.

مهم جداً:

1- لو المستخدم بيسأل على فيلم أو مسلسل موجود بعينه:
مثال:
جون ويك
breaking bad
interstellar
الحريفة

لا ترشح أفلام.

رد فقط بهذا الشكل:

SEARCH:
اسم العمل الرسمي فقط

أمثلة:

SEARCH: John Wick
SEARCH: Breaking Bad
SEARCH: Interstellar

=====================

2- لو المستخدم طالب ترشيحات:

أمثلة:

رشحلي أفلام أكشن
عايز مسلسل رعب
فيلم مصري حلو
افلام جديدة
مسلسلات جريمة

ارجع JSON فقط:

{{
  "titles": [
    "title1",
    "title2",
    "title3",
    "title4",
    "title5"
  ]
}}

القواعد:

- رجع 5 فقط.
- اختار أعمال قوية.
- متكررش نفس الترشيحات كل مرة.
- لو طلب جديد اختار أعمال حديثة.
- لو طلب عربي رجع عربي فقط.
- لو طلب أجنبي رجع أجنبي فقط.
- لو طلب مسلسل رجع مسلسلات فقط.
- لو طلب فيلم رجع أفلام فقط.

=====================

3- لو المستخدم بيتكلم عادي:

مثال:

عامل ايه
ازيك
مين انت
احكيلي نكتة

رد بشكل طبيعي كشات عادي.

ممنوع ترجع JSON هنا.

=====================

4- لو المستخدم سأل سؤال عام:

رد عليه بشكل طبيعي.

=====================

المهم جداً:

- عند البحث عن فيلم أو مسلسل محدد ارجع SEARCH فقط.
- عند الترشيحات ارجع JSON فقط.
- عند الدردشة العادية ارجع كلام عادي فقط.
- ممنوع تخلط بينهم.

رسالة المستخدم:

{user_text}
"""

        # =========================================
        # 🤖 Gemini
        # =========================================

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=full_prompt
        )

        # ❌ مفيش رد
        if not response or not response.text:

            bot.reply_to(
                message,
                "معلش يا صاحبي دماغي هنجت شوية 🤯"
            )

            return

        reply = response.text.strip()
        #search
        if reply.startswith("SEARCH:"):
            title = reply.replace(
            "SEARCH","").strip()
            try:
                ai_show_movie(
                chat_id=message.chat.id,
                title=title,
                reply_to=message.message_id)
            except Exception as e:
                print (
                "SEARCH ERROR:",
                e)
                bot.reply_to(
                message,
                "مش لاقي المطلوب لاسف 🥺")
                return

        # =========================================
        # 🎬 محاولة فهم JSON
        # =========================================

        try:

            data = json.loads(reply)

            titles = data.get("titles", [])

        except:

            titles = []

        # =========================================
        # 🎥 ترشيحات
        # =========================================

        if titles:

            bot.send_message(
                message.chat.id,
                "يتم تجهيز الترشيحات شوية صبر ❤️،،وهتكون عندك !"
            )

            for title in titles:

                try:

                    ai_show_movie(
                        chat_id=message.chat.id,
                        title=title,
                        reply_to=message.message_id
                    )

                except Exception as e:

                    print("AI MOVIE ERROR:", e)

            return

        # =========================================
        # 💬 شات عادي
        # =========================================

        bot.reply_to(
            message,
            reply
        )

    # =========================================
    # ❌ ERROR
    # =========================================

    except Exception as e:

        print("AI ERROR:", e)

        bot.send_message(
            message.chat.id,
            "استنى عليا بس يا نجم 😅🔥\n"
            "في ضغط رهيب عليا دلوقتي وانا مطلوب جداً 😂\n"
            "تعالى كمان شوية وهنروق الدنيا سوا 💪"
        )
def start_broadcast(message):
    if message.chat.id == ADMIN_ID:
        # بنستخدم زرار "إلغاء" عشان لو غيرت رأيك
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("❌ إلغاء الإذاعة")
        
        bot.send_message(ADMIN_ID, "📢 ابعت دلوقتي (أي حاجة): نص، استيكر، صورة، أو حتى فيديو..\nوهتوصل للكل زي ما هي بالضبط!", reply_markup=markup)
        bot.register_next_step_handler(message, broadcast_to_all)

def broadcast_to_all(message):
    if message.text == "❌ إلغاء الإذاعة":
        bot.send_message(ADMIN_ID, "✅ تم إلغاء الإذاعة يصحبي.", reply_markup=types.ReplyKeyboardRemove())
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        sent = 0
        failed = 0

        # بنعرف الأدمن إن العملية بدأت
        status_msg = bot.send_message(ADMIN_ID, "🚀 بدأت عملية الإذاعة.. خليك معايا.")

        for user in users:
            user_id = user[0]
            if user_id == ADMIN_ID: continue # عشان ميبعتش لنفسك مرتين

            try:
                # 💡 الزتونة هنا: copy_message بتنسخ أي نوع رسالة (حتى الاستيكرات البريميوم)
                bot.copy_message(chat_id=user_id, from_chat_id=ADMIN_ID, message_id=message.message_id)
                sent += 1
                
                # تريكة المبرمجين: بنخلي البوت ياخد نفسه (Rest) كل شوية عشان ميتجمدش
                if sent % 20 == 0:
                    time.sleep(1) 

            except:
                failed += 1

        # ✅ التقرير النهائي
        bot.send_message(
            ADMIN_ID,
            f"📊 **تقرير الإذاعة النهائي**\n\n"
            f"✅ تم الإرسال بنجاح: {sent}\n"
            f"❌ فشل (مستخدمين عملوا بلوك): {failed}\n"
            f"📦 الإجمالي: {sent + failed}",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove()
        )

    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطأ كارثي في الإذاعة: {str(e)}")
        

@bot.message_handler(func=lambda message: message.chat.type == "private" and message.from_user.id != ADMIN_ID, 
                     content_types=['text', 'video', 'photo', 'document'])
def handle_user_message(message):
    user_id = message.from_user.id
    user = message.from_user
    username = f"@{user.username}" if user.username else "بدون يوزر"

    is_vip = False  # القيمة الافتراضية

    # 1️⃣ تسجيل المستخدم في جدول users العام وعمل النسخة الاحتياطية
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        
        # 2️⃣ التحقق "البسيط": هل المستخدم موجود في جدول المشتركين؟
        cursor.execute("SELECT 1 FROM subscriptions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            is_vip = True  # موجود في الجدول إذن هو VIP
        
        conn.close()
        backup_database()
    except Exception as e:
        print(f"Database Error: {e}")

    # 3️⃣ تجهيز زر الرد للأدمن
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎯 رد عليه", callback_data=f"reply_{user_id}"))

    # 4️⃣ المنطق الخاص بالرسائل والروابط
    if message.text:
        if "http" in message.text:
            # التحقق من وجوده في جدول الاشتراكات
            if not is_vip:
                bot.send_message(
                    message.chat.id, 
                    "عذراً يا بطل! 🌟 هذه الميزة متاحة فقط للمشتركين المميزين (VIP).\n\n"
                    "تواصل مع المطور للاشتراك واستمتع بالخدمة! 👑✨",
                    reply_to_message_id=message.message_id
                )
                # إشعار للأدمن
                bot.send_message(ADMIN_ID, f"🚫 محاولة تحميل من غير مشترك:\nالاسم: {user.first_name}\nID: `{user_id}`")
                return

            # لو موجود في الجدول (is_vip = True)
            admin_info = (
                f"🌟 **طلب تحميل جديد (VIP)**\n\n"
                f"👤 الاسم: {user.first_name}\n"
                f"🆔 الآيدي: `{user_id}`\n"
                f"🏷 اليوزر: {username}\n"
                f"🌐 الرابط: {message.text.strip()}"
            )
            bot.send_message(ADMIN_ID, admin_info, parse_mode="Markdown", reply_markup=markup)
            
            t = threading.Thread(target=process_video, args=(message,))
            t.start()
            
        else:
            # رسالة نصية عادية
            bot.send_message(
                ADMIN_ID,
                f"📩 **رسالة نصية من:** {user.first_name}\n🆔 الآيدي: `{user_id}`\n\n{message.text}",
                parse_mode="Markdown",
                reply_markup=markup
            )

    # 5️⃣ التعامل مع الميديا
    elif message.video:
        bot.send_video(ADMIN_ID, message.video.file_id, 
                        caption=f"🎥 فيديو من {user.first_name}\n🆔 `{user_id}`", 
                        reply_markup=markup)
    
    elif message.photo:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
                        caption=f"🖼 صورة من {user.first_name}\n🆔 `{user_id}`", 
                        reply_markup=markup)
    
    elif message.document:
        bot.send_document(ADMIN_ID, message.document.file_id, 
                          caption=f"📎 ملف من {user.first_name}\n🆔 `{user_id}`", 
                          reply_markup=markup)
# =========================================================
# 🌐 Koyeb Health Check Server
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    print("🌐 HEALTH CHECK OK")
    return "OK", 200


def run_server():
    port = int(os.environ.get("PORT", 8000))

    print(f"🌐 Starting Flask server on port {port}")

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# 🚀 START EVERYTHING
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("🚀 BOT STARTING...")
    print("=" * 60)

    # =====================================================
    # 🌐 Flask / Koyeb
    # =====================================================

    try:

        health_thread = threading.Thread(
            target=run_server,
            daemon=True,
            name="HealthServerThread"
        )

        health_thread.start()

        print("✅ Health server thread started")

    except Exception as e:

        print(
            "❌ HEALTH SERVER ERROR:",
            repr(e)
        )


    # =====================================================
    # 💾 AUTO BACKUP
    # =====================================================

    try:

        print("💾 Starting automatic backup...")

        backup_thread = threading.Thread(
            target=start_auto_backup,
            args=(
                bot,
                DB_NAME,
                backup_conn,
                get_uptime,
                lambda: get_total_users(DB_NAME),
                lambda: get_total_content(DB_NAME),
                lambda: get_total_links(DB_NAME)
            ),
            daemon=True,
            name="AutoBackupThread"
        )

        backup_thread.start()

        print(
            "✅ Automatic backup thread started | "
            f"alive={backup_thread.is_alive()}"
        )

    except Exception as e:

        print(
            "❌ AUTO BACKUP THREAD ERROR:",
            repr(e)
        )


    # =====================================================
    # 🎬 RECOMMENDATION SYSTEM
    # =====================================================

    try:

        print("🎬 Starting recommendation system...")

        recommendation_thread = threading.Thread(
            target=recommendation_loop,
            daemon=True,
            name="RecommendationThread"
        )

        recommendation_thread.start()

        print(
            "✅ Recommendation thread started | "
            f"alive={recommendation_thread.is_alive()}"
        )

    except Exception as e:

        print(
            "❌ RECOMMENDATION THREAD ERROR:",
            repr(e)
        )


    # =====================================================
    # 🤖 TELEGRAM BOT CHECK
    # =====================================================

    print(
        "🧪 BEFORE GET_ME",
        flush=True
    )

    try:

        print(
            "🧪 CALLING TELEGRAM get_me...",
            flush=True
        )

        me = bot.get_me()

        print(
            "🧪 AFTER GET_ME",
            flush=True
        )

        print(
            f"🤖 TELEGRAM BOT OK | "
            f"ID={me.id} | "
            f"USERNAME=@{me.username}",
            flush=True
        )

    except Exception as e:

        print(
            "❌ TELEGRAM CONNECTION ERROR:",
            repr(e),
            flush=True
        )


    # =====================================================
    # 🧹 REMOVE WEBHOOK
    # =====================================================

    try:

        print(
            "🧹 Removing webhook...",
            flush=True
        )

        bot.remove_webhook()

        print(
            "✅ Webhook removed",
            flush=True
        )

    except Exception as e:

        print(
            "❌ WEBHOOK ERROR:",
            repr(e),
            flush=True
        )


    # =====================================================
    # 📡 TELEGRAM POLLING
    # =====================================================

    print("=" * 60)
    print(
        "📡 TELEGRAM POLLING STARTING...",
        flush=True
    )
    print("=" * 60)

    while True:

        try:

            print(
                "🟢 POLLING IS RUNNING...",
                flush=True
            )

            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60
            )

            print(
                "⚠️ infinity_polling stopped normally!",
                flush=True
            )

        except Exception as e:

            print("=" * 60, flush=True)
            print(
                "❌ TELEGRAM POLLING CRASH ❌",
                flush=True
            )
            print(
                "ERROR:",
                repr(e),
                flush=True
            )
            print("=" * 60, flush=True)

            print(
                "🔄 Restarting polling in 15 seconds...",
                flush=True
            )

            time.sleep(15)

            print(
                "🔁 RETRYING TELEGRAM POLLING...",
                flush=True
            )

            time.sleep(15)

            print(
                "🔁 RETRYING TELEGRAM POLLING..."
            )
