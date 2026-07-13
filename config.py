# -*- coding: utf-8 -*-
import os

# ===========================
# تنظیمات اصلی ربات
# ===========================

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# آیدی کانال (مثلاً @mychannel یا -1001234567890)
CHANNEL_ID: str = os.environ["CHANNEL_ID"]

# لینک دعوت به کانال (برای دکمه عضویت)
CHANNEL_LINK: str = os.environ["CHANNEL_LINK"]

# آیدی‌های عددی ادمین‌ها، جداشده با ویرگول
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()
]

# اطلاعات کارت بانکی
CARD_NUMBER: str = os.environ["CARD_NUMBER"]
CARD_OWNER: str = os.environ["CARD_OWNER"]

# مسیر فایل دیتابیس
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "bot_data.db")

# فاصله زمانی بررسی timeout (دقیقه)
TIMEOUT_CHECK_INTERVAL_MINUTES: int = int(os.environ.get("TIMEOUT_CHECK_INTERVAL_MINUTES", "30"))

# مدت زمان تأیید فروشنده (ساعت)
SELLER_CONFIRM_TIMEOUT_HOURS: int = int(os.environ.get("SELLER_CONFIRM_TIMEOUT_HOURS", "72"))
