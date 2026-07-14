# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


# ===========================
# کیبوردهای اینلاین
# ===========================

def channel_join_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=channel_link)],
        [InlineKeyboardButton("✅ بررسی مجدد عضویت", callback_data="check_membership")],
    ])


def warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ متوجه شدم", callback_data="accept_warning")],
    ])


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("📢 ثبت آگهی فروش"), KeyboardButton("🛒 خرید اکانت")],
        [KeyboardButton("📋 آگهی‌های من")],
    ]
    if is_admin:
        buttons.append([KeyboardButton("⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


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
        [InlineKeyboardButton("❌ خیر، همان بماند", callback_data="email_no")],
    ])


def sell_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ لغو", callback_data="cancel_sell")],
    ])


def admin_receipt_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید پرداخت", callback_data=f"admin_approve_{transaction_id}"),
            InlineKeyboardButton("❌ رد پرداخت", callback_data=f"admin_reject_{transaction_id}"),
        ]
    ])


def seller_confirm_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید تحویل اکانت", callback_data=f"seller_confirm_{transaction_id}")],
    ])


def my_listings_keyboard(listings: list) -> InlineKeyboardMarkup:
    rows = []
    for lst in listings:
        status_icon = "🟢" if lst["status"] == "active" else ("🟡" if lst["status"] == "reserved" else "🔴")
        rows.append([
            InlineKeyboardButton(
                f"{status_icon} {lst['title']} — {lst['unique_code']}",
                callback_data=f"view_listing_{lst['id']}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def listing_actions_keyboard(listing_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("active", "reserved"):
        rows.append([
            InlineKeyboardButton("🗑 حذف آگهی", callback_data=f"delete_listing_{listing_id}")
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="my_listings_back")])
    return InlineKeyboardMarkup(rows)


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🚫 لیست کاربران مسدود"), KeyboardButton("✅ رفع مسدودیت کاربر")],
        [KeyboardButton("📋 مدیریت آگهی‌ها"), KeyboardButton("🔍 جستجوی آگهی")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def admin_listings_filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 فعال", callback_data="admin_listings_active"),
            InlineKeyboardButton("🟡 رزرو", callback_data="admin_listings_reserved"),
        ],
        [
            InlineKeyboardButton("🔴 غیرفعال", callback_data="admin_listings_inactive"),
            InlineKeyboardButton("📋 همه", callback_data="admin_listings_all"),
        ],
    ])


def admin_listings_keyboard(listings: list) -> InlineKeyboardMarkup:
    rows = []
    for lst in listings[:20]:  # حداکثر ۲۰ آگهی نشان داده می‌شود
        status_icon = {"active": "🟢", "reserved": "🟡", "inactive": "🔴", "sold": "✅"}.get(lst["status"], "❓")
        rows.append([
            InlineKeyboardButton(
                f"{status_icon} {lst['title'][:25]} — {lst['unique_code']}",
                callback_data=f"admin_view_listing_{lst['id']}",
            )
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_listings_back")])
    return InlineKeyboardMarkup(rows)


def admin_listing_actions_keyboard(listing_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("active", "reserved"):
        rows.append([
            InlineKeyboardButton("🗑 غیرفعال‌کردن آگهی", callback_data=f"admin_deactivate_{listing_id}"),
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="admin_listings_all")])
    return InlineKeyboardMarkup(rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت", callback_data="go_back_main")]
    ])
