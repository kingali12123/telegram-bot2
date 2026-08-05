# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# دسته‌بندی‌های پشتیبانی‌شده
CATEGORIES: dict[str, str] = {
    "coc_account": "⚔️ اکانت کلش آف کلنز",
    "coc_clan":    "🏰 کلن کلش آف کلنز",
    "freefire":    "🔥 اکانت فری‌فایر",
    "codm":        "🎯 اکانت کالاف دیوتی موبایل",
}
CLAN_CATEGORIES = {"coc_clan"}


def channel_join_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    buttons = []
    if channel_link:
        buttons.append([InlineKeyboardButton("📢 عضویت در کانال", url=channel_link)])
    buttons.append([InlineKeyboardButton("✅ بررسی مجدد عضویت", callback_data="check_membership")])
    return InlineKeyboardMarkup(buttons)


def warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ متوجه شدم", callback_data="accept_warning")]])


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📢 ثبت آگهی فروش"), KeyboardButton("🛒 خرید اکانت/کلن")],
        [KeyboardButton("👛 کیف پول من"),       KeyboardButton("📋 آگهی‌های من")],
        [KeyboardButton("🔗 دعوت از دوستان")],
    ]
    if is_admin:
        buttons.append([KeyboardButton("⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# ===========================
# کیبوردهای فروش
# ===========================

def sell_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ اکانت کلش آف کلنز", callback_data="cat_coc_account")],
        [InlineKeyboardButton("🏰 کلن کلش آف کلنز",   callback_data="cat_coc_clan")],
        [InlineKeyboardButton("🔥 اکانت فری‌فایر",     callback_data="cat_freefire")],
        [InlineKeyboardButton("🎯 اکانت کالاف دیوتی",  callback_data="cat_codm")],
        [InlineKeyboardButton("❌ لغو",                callback_data="cancel_sell")],
    ])


def sell_end_photos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ پایان ارسال تصاویر", callback_data="end_photos")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_sell")],
    ])


def sell_skip_video_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ رد کردن ویدیو", callback_data="skip_video")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_sell")],
    ])


def sell_email_change_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، ایمیل عوض شود", callback_data="email_yes")],
        [InlineKeyboardButton("❌ خیر، همان بماند",    callback_data="email_no")],
    ])


def sell_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_sell")]])


# ===========================
# کیبوردهای ادمین — آگهی
# ===========================

def admin_listing_approval_keyboard(listing_id: int) -> InlineKeyboardMarkup:
    """تأیید یا رد آگهی قبل از انتشار در کانال."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ انتشار در کانال", callback_data=f"listing_approve_{listing_id}"),
            InlineKeyboardButton("❌ رد آگهی",         callback_data=f"listing_reject_{listing_id}"),
        ]
    ])


def admin_receipt_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید پرداخت", callback_data=f"admin_approve_{transaction_id}"),
            InlineKeyboardButton("❌ رد پرداخت",    callback_data=f"admin_reject_{transaction_id}"),
        ]
    ])


def admin_wallet_charge_keyboard(charge_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید شارژ", callback_data=f"wcharge_approve_{charge_id}"),
            InlineKeyboardButton("❌ رد شارژ",    callback_data=f"wcharge_reject_{charge_id}"),
        ]
    ])


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🚫 لیست کاربران مسدود"), KeyboardButton("✅ رفع مسدودیت کاربر")],
        [KeyboardButton("📋 مدیریت آگهی‌ها"),      KeyboardButton("🔍 جستجوی آگهی")],
        [KeyboardButton("💰 گزارش مالی"),           KeyboardButton("🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def admin_listings_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 فعال",    callback_data="admin_listings_active"),
            InlineKeyboardButton("🟡 رزرو",    callback_data="admin_listings_reserved"),
        ],
        [
            InlineKeyboardButton("⏳ در انتظار", callback_data="admin_listings_draft"),
            InlineKeyboardButton("📋 همه",      callback_data="admin_listings_all"),
        ],
        [
            InlineKeyboardButton("🔴 غیرفعال", callback_data="admin_listings_inactive"),
            InlineKeyboardButton("✅ فروخته",   callback_data="admin_listings_sold"),
        ],
    ])


def admin_listings_keyboard(listings: list) -> InlineKeyboardMarkup:
    STATUS_ICON = {"active": "🟢", "reserved": "🟡", "inactive": "🔴", "sold": "✅", "draft": "⏳", "rejected": "❌"}
    rows = []
    for lst in listings[:20]:
        icon = STATUS_ICON.get(lst["status"], "❓")
        rows.append([InlineKeyboardButton(
            f"{icon} {lst['title'][:25]} — {lst['unique_code']}",
            callback_data=f"admin_view_listing_{lst['id']}",
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_listings_back")])
    return InlineKeyboardMarkup(rows)


def admin_listing_actions_keyboard(listing_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("active", "reserved"):
        rows.append([InlineKeyboardButton(
            "🗑 حذف از کانال و غیرفعال‌کردن",
            callback_data=f"admin_deactivate_{listing_id}",
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="admin_listings_all")])
    return InlineKeyboardMarkup(rows)


# ===========================
# کیبوردهای فروشنده / خریدار
# ===========================

def seller_confirm_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید تحویل اکانت", callback_data=f"seller_confirm_{transaction_id}")]
    ])


def buyer_confirm_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ اکانت رو دریافت کردم", callback_data=f"buyer_confirm_{transaction_id}")],
        [InlineKeyboardButton("⚠️ مشکل دارم",           callback_data=f"buyer_dispute_{transaction_id}")],
    ])


def buy_payment_method_keyboard(has_enough_wallet: bool, buyer_amount: int, wallet_balance: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💳 پرداخت با کارت بانکی", callback_data="pay_card")],
    ]
    if has_enough_wallet:
        rows.append([InlineKeyboardButton(
            f"👛 پرداخت با کیف پول (موجودی: {wallet_balance:,} ت)",
            callback_data="pay_wallet",
        )])
    else:
        rows.append([InlineKeyboardButton(
            f"👛 کیف پول (موجودی ناکافی: {wallet_balance:,} از {buyer_amount:,} ت)",
            callback_data="wallet_insufficient",
        )])
    rows.append([InlineKeyboardButton("❌ لغو", callback_data="cancel_buy")])
    return InlineKeyboardMarkup(rows)


# ===========================
# کیبوردهای کیف پول
# ===========================

def wallet_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_wallet")]])


# ===========================
# کیبوردهای آگهی‌های من
# ===========================

def my_listings_keyboard(listings: list) -> InlineKeyboardMarkup:
    STATUS_ICON = {"active": "🟢", "reserved": "🟡", "sold": "✅", "draft": "⏳", "rejected": "❌"}
    rows = []
    for lst in listings:
        icon = STATUS_ICON.get(lst["status"], "🔴")
        rows.append([InlineKeyboardButton(
            f"{icon} {lst['title']} — {lst['unique_code']}",
            callback_data=f"view_listing_{lst['id']}",
        )])
    return InlineKeyboardMarkup(rows)


def listing_actions_keyboard(listing_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("active", "reserved"):
        rows.append([InlineKeyboardButton("🗑 حذف آگهی", callback_data=f"delete_listing_{listing_id}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="my_listings_back")])
    return InlineKeyboardMarkup(rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="go_back_main")]])
