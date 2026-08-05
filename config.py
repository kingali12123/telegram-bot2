# -*- coding: utf-8 -*-
import os

# ===========================
# تنظیمات اصلی ربات
# ===========================

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

CHANNEL_ID: str = os.environ["CHANNEL_ID"]
CHANNEL_LINK: str = os.environ.get("CHANNEL_LINK", "")

ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()
]

BOT_USERNAME: str = os.environ.get("BOT_USERNAME", "")

# اطلاعات کارت بانکی (پشتیبانی از هر دو نام متغیر)
CARD_NUMBER: str = os.environ.get("CARD_NUMBER") or os.environ.get("PAYMENT_CARD_NUMBER", "")
CARD_OWNER: str  = os.environ.get("CARD_OWNER", "")

DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "bot_data.db")

# ===========================
# کارمزد واسط‌گری
# ===========================
# از خریدار ۱۰٪ بیشتر از قیمت پایه دریافت می‌شود
BUYER_COMMISSION_PCT: int = int(os.environ.get("BUYER_COMMISSION_PCT", "10"))
# از سهم فروشنده ۵٪ کسر می‌شود
SELLER_COMMISSION_PCT: int = int(os.environ.get("SELLER_COMMISSION_PCT", "5"))

# ===========================
# سیستم رفرال
# ===========================
REFERRAL_THRESHOLD: int   = int(os.environ.get("REFERRAL_THRESHOLD", "5"))
REFERRAL_REWARD_TOMAN: int = int(os.environ.get("REFERRAL_REWARD_TOMAN", "40000"))

# ===========================
# Timeout ها
# ===========================
TIMEOUT_CHECK_INTERVAL_MINUTES: int = int(os.environ.get("TIMEOUT_CHECK_INTERVAL_MINUTES", "30"))
SELLER_CONFIRM_TIMEOUT_HOURS: int   = int(os.environ.get("SELLER_CONFIRM_TIMEOUT_HOURS", "72"))
BUYER_CONFIRM_TIMEOUT_HOURS: int    = int(os.environ.get("BUYER_CONFIRM_TIMEOUT_HOURS", "72"))

# ===========================
# سرور health-check
# ===========================
HEALTH_PORT: int = int(os.environ.get("PORT", "8080"))
RENDER_EXTERNAL_URL: str = os.environ.get("RENDER_EXTERNAL_URL", "")
