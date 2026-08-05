# -*- coding: utf-8 -*-
"""ربات واسطه خرید و فروش اکانت/کلن بازی — نقطه ورود اصلی"""
import logging
import socket
import threading
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InputMediaPhoto, Bot
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    BOT_USERNAME,
    BUYER_CONFIRM_TIMEOUT_HOURS,
    CARD_NUMBER,
    CARD_OWNER,
    CHANNEL_ID,
    CHANNEL_LINK,
    HEALTH_PORT,
    REFERRAL_REWARD_TOMAN,
    REFERRAL_THRESHOLD,
    RENDER_EXTERNAL_URL,
    SELLER_CONFIRM_TIMEOUT_HOURS,
    TIMEOUT_CHECK_INTERVAL_MINUTES,
)
from keyboards import (
    CATEGORIES,
    CLAN_CATEGORIES,
    admin_listing_actions_keyboard,
    admin_listing_approval_keyboard,
    admin_listings_filter_keyboard,
    admin_listings_keyboard,
    admin_panel_keyboard,
    admin_receipt_keyboard,
    admin_wallet_charge_keyboard,
    buy_payment_method_keyboard,
    buyer_confirm_keyboard,
    channel_join_keyboard,
    listing_actions_keyboard,
    main_menu_keyboard,
    my_listings_keyboard,
    sell_cancel_keyboard,
    sell_category_keyboard,
    sell_email_change_keyboard,
    sell_end_photos_keyboard,
    sell_skip_video_keyboard,
    seller_confirm_keyboard,
    wallet_cancel_keyboard,
    warning_keyboard,
)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ====================================================
# شماره مراحل مکالمه
# ====================================================

# فروش (0-14)
(
    SELL_CATEGORY,
    SELL_TITLE,
    SELL_DESCRIPTION,
    SELL_PRICE,
    SELL_PHOTOS,
    SELL_VIDEO,
    SELL_EMAIL,
    SELL_PASSWORD,
    SELL_EMAIL_CHANGE_Q,
    SELL_NEW_EMAIL,
    SELL_PHONE,
    SELL_CLAN_NAME,
    SELL_CLAN_LEVEL,
    SELL_CLAN_MEMBERS,
    SELL_CLAN_TROPHIES,
) = range(15)

# خرید (15-17)
BUY_ENTER_CODE      = 15
BUY_PAYMENT_METHOD  = 16
BUY_SEND_RECEIPT    = 17

# کیف پول (18-19)
WALLET_ENTER_AMOUNT = 18
WALLET_SEND_RECEIPT = 19

# ادمین (20-21)
ADMIN_WAIT_UNBAN_ID    = 20
ADMIN_WAIT_SEARCH_CODE = 21

# وضعیت فارسی آگهی
STATUS_FA = {
    "draft":    "⏳ در انتظار تأیید ادمین",
    "active":   "🟢 فعال",
    "reserved": "🟡 در حال خرید",
    "inactive": "🔴 غیرفعال",
    "sold":     "✅ فروخته شده",
    "rejected": "❌ رد شده",
}


# ====================================================
# Health-check HTTP server
# ====================================================

class _HealthHandler(BaseHTTPRequestHandler):
    def _send_ok(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self) -> None:   self._send_ok()         # noqa: E704
    def do_HEAD(self) -> None:                           # noqa: E704
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
    def log_message(self, *args) -> None: pass           # سرکوب لاگ نویز


def _start_health_server() -> None:
    while True:
        try:
            server = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            logger.info("Health-check server started on port %d", HEALTH_PORT)
            server.serve_forever()
        except Exception as exc:
            logger.error("Health-check server crashed (%s) — restarting in 5s…", exc)
            time.sleep(5)


# ====================================================
# توابع کمکی مشترک
# ====================================================

async def is_member(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        return False


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user is None:
        return False
    db.upsert_user(user.id, user.username, user.full_name)
    if db.is_banned(user.id):
        await update.effective_message.reply_text(
            "⛔ دسترسی شما به ربات مسدود شده است.\n"
            "در صورت اعتراض با ادمین تماس بگیرید."
        )
        return False
    if not await is_member(context.bot, user.id):
        await update.effective_message.reply_text(
            "📢 برای استفاده از ربات باید عضو کانال ما باشید.\n"
            "پس از عضویت روی «بررسی مجدد» بزنید:",
            reply_markup=channel_join_keyboard(CHANNEL_LINK),
        )
        return False
    user_row = db.get_user(user.id)
    if user_row and not user_row["warned"]:
        await update.effective_message.reply_text(
            "⚠️ <b>هشدار مهم</b>\n\n"
            "در صورتی که مشخص شود قصد کلاهبرداری دارید یا اطلاعات نادرست ارائه می‌دهید، "
            "دسترسی شما برای همیشه مسدود می‌شود و مشخصات شما در اختیار سایر کاربران قرار می‌گیرد.\n\n"
            "برای ادامه استفاده از ربات تأیید کنید:",
            reply_markup=warning_keyboard(),
            parse_mode="HTML",
        )
        return False
    return True


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = "منوی اصلی:") -> None:
    user_id = update.effective_user.id
    await update.effective_message.reply_text(
        text, reply_markup=main_menu_keyboard(is_admin=is_admin(user_id))
    )


def _bot_link() -> str:
    return f"@{BOT_USERNAME}" if BOT_USERNAME else ""


def _fmt(amount: int | None) -> str:
    return f"{amount:,} تومان" if amount else "—"


async def _notify_admins(bot: Bot, text: str, **kwargs) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except Exception:
            pass


async def _publish_listing_to_channel(bot: Bot, listing_id: int) -> bool:
    """پابلیش آگهی در کانال پس از تأیید ادمین. برمی‌گرداند True اگه موفق بود."""
    listing = db.get_listing_by_id(listing_id)
    if not listing:
        return False
    media = db.get_listing_media(listing_id)
    photos = [m["file_id"] for m in media if m["media_type"] == "photo"]
    video  = next((m["file_id"] for m in media if m["media_type"] == "video"), None)

    cat_label = CATEGORIES.get(listing["category"], listing["category"])
    price_toman = listing["price_toman"]
    price_display = listing["price"] or (db.fmt_price(price_toman) if price_toman else "")
    price_line = f"💰 قیمت پایه: <b>{price_display}</b>\n" if price_display else ""

    if price_toman:
        buyer_pays, _, _ = db.calculate_commission(price_toman)
        price_line += f"🧾 مبلغ نهایی خریدار (با کارمزد): <b>{db.fmt_price(buyer_pays)}</b>\n"

    bot_line = f"\n🤖 ربات: {_bot_link()}" if _bot_link() else ""
    unique_code = listing["unique_code"]

    # اطلاعات اضافی برای کلن
    clan_info = ""
    if listing["category"] == "coc_clan":
        parts = []
        if listing["clan_name"]:    parts.append(f"🏰 نام کلن: <b>{listing['clan_name']}</b>")
        if listing["clan_level"]:   parts.append(f"🎖 لول کلن: {listing['clan_level']}")
        if listing["member_count"]: parts.append(f"👥 اعضا: {listing['member_count']}")
        if listing["clan_trophies"]:parts.append(f"🏆 تراف: {listing['clan_trophies']}")
        clan_info = "\n".join(parts) + "\n\n" if parts else ""

    text = (
        f"🎮 [{cat_label}] <b>{listing['title']}</b>\n\n"
        f"📝 {listing['description']}\n\n"
        f"{clan_info}"
        f"{price_line}"
        f"🔑 کد یکتای آگهی: <code>{unique_code}</code>\n\n"
        f"برای خرید، کد بالا را در ربات وارد کنید.{bot_line}"
    )

    sent_msg = None
    try:
        if len(photos) == 1:
            sent_msg = await bot.send_photo(CHANNEL_ID, photo=photos[0], caption=text, parse_mode="HTML")
        elif len(photos) > 1:
            group = [InputMediaPhoto(photos[0], caption=text, parse_mode="HTML")]
            group += [InputMediaPhoto(p) for p in photos[1:]]
            msgs = await bot.send_media_group(CHANNEL_ID, group)
            sent_msg = msgs[0]
        elif video:
            sent_msg = await bot.send_video(CHANNEL_ID, video=video, caption=text, parse_mode="HTML")
        else:
            sent_msg = await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.error("خطا در انتشار کانال: %s", e)
        return False

    if sent_msg:
        db.set_channel_msg_id(listing_id, sent_msg.message_id)
    db.approve_listing(listing_id)
    return True


# ====================================================
# /start و عضویت
# ====================================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.full_name)

    # پردازش لینک رفرال: /start ref_<user_id>
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg[4:])
                if referrer_id != user.id:
                    registered = db.set_referrer(user.id, referrer_id)
                    if registered:
                        # بررسی آستانه پاداش
                        count = db.get_referral_count(referrer_id)
                        if count > 0 and count % REFERRAL_THRESHOLD == 0:
                            db.credit_wallet(
                                referrer_id,
                                REFERRAL_REWARD_TOMAN,
                                "referral",
                                note=f"پاداش دعوت ({count} زیرمجموعه)",
                            )
                            try:
                                await context.bot.send_message(
                                    referrer_id,
                                    f"🎉 <b>پاداش دعوت!</b>\n\n"
                                    f"به خاطر دعوت {count} نفر، "
                                    f"<b>{_fmt(REFERRAL_REWARD_TOMAN)}</b> به کیف پول شما اضافه شد! 🎁",
                                    parse_mode="HTML",
                                )
                            except Exception:
                                pass
                            # اطلاع ادمین
                            referrer = db.get_user(referrer_id)
                            rname = referrer["full_name"] if referrer else str(referrer_id)
                            rusername = f" (@{referrer['username']})" if referrer and referrer["username"] else ""
                            await _notify_admins(
                                context.bot,
                                f"🔔 <b>پاداش رفرال پرداخت شد</b>\n\n"
                                f"کاربر: {rname}{rusername}\n"
                                f"آیدی: <code>{referrer_id}</code>\n"
                                f"زیرمجموعه‌های فعال: {count}\n"
                                f"پاداش: {_fmt(REFERRAL_REWARD_TOMAN)}",
                                parse_mode="HTML",
                            )
            except (ValueError, IndexError):
                pass

    if db.is_banned(user.id):
        await update.message.reply_text("⛔ دسترسی شما مسدود شده است.")
        return

    if not await is_member(context.bot, user.id):
        await update.message.reply_text(
            "👋 سلام!\n\n📢 برای استفاده باید عضو کانال ما باشید.\n"
            "پس از عضویت روی «بررسی مجدد» بزنید:",
            reply_markup=channel_join_keyboard(CHANNEL_LINK),
        )
        return

    user_row = db.get_user(user.id)
    if user_row and not user_row["warned"]:
        await update.message.reply_text(
            "⚠️ <b>هشدار مهم</b>\n\n"
            "در صورتی که مشخص شود قصد کلاهبرداری دارید یا اطلاعات نادرست ارائه می‌دهید، "
            "دسترسی شما برای همیشه مسدود می‌شود.\n\n"
            "برای ادامه تأیید کنید:",
            reply_markup=warning_keyboard(),
            parse_mode="HTML",
        )
        return

    await send_main_menu(update, context, f"👋 سلام {user.first_name}!\nبه ربات خوش آمدید:")


async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if db.is_banned(user.id):
        await query.edit_message_text("⛔ دسترسی شما مسدود شده است.")
        return
    if not await is_member(context.bot, user.id):
        await query.answer("❌ هنوز عضو کانال نشده‌اید!", show_alert=True)
        return
    user_row = db.get_user(user.id)
    if user_row and not user_row["warned"]:
        await query.edit_message_text(
            "⚠️ <b>هشدار مهم</b>\n\n"
            "در صورتی که مشخص شود قصد کلاهبرداری دارید، دسترسی مسدود می‌شود.\n\n"
            "برای ادامه تأیید کنید:",
            reply_markup=warning_keyboard(),
            parse_mode="HTML",
        )
        return
    await query.edit_message_text("✅ عضویت تأیید شد!")
    await context.bot.send_message(
        user.id, f"👋 سلام {user.first_name}!\nبه ربات خوش آمدید:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


async def accept_warning_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    db.set_warned(user.id)
    await query.edit_message_text("✅ تأیید شد. خوش آمدید!")
    await context.bot.send_message(
        user.id, f"👋 سلام {user.first_name}!\nبه ربات خوش آمدید:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


# ====================================================
# دعوت از دوستان (رفرال)
# ====================================================

async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_access(update, context):
        return
    user = update.effective_user
    count = db.get_referral_count(user.id)
    next_reward = REFERRAL_THRESHOLD - (count % REFERRAL_THRESHOLD)
    bot_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}" if BOT_USERNAME else f"/start ref_{user.id}"
    await update.message.reply_text(
        f"🔗 <b>سیستم دعوت از دوستان</b>\n\n"
        f"لینک اختصاصی شما:\n<code>{bot_link}</code>\n\n"
        f"👥 زیرمجموعه‌های فعال شما: <b>{count}</b>\n"
        f"🎁 هر {REFERRAL_THRESHOLD} نفر → <b>{_fmt(REFERRAL_REWARD_TOMAN)}</b> به کیف پول\n\n"
        f"⏭ تا پاداش بعدی: <b>{next_reward}</b> نفر دیگر لازم دارید\n\n"
        "لینک را با دوستانتان به اشتراک بگذارید!",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


# ====================================================
# کیف پول — شارژ
# ====================================================

async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_access(update, context):
        return
    user = update.effective_user
    balance = db.get_wallet_balance(user.id)
    txs = db.get_wallet_transactions(user.id, limit=5)
    tx_lines = ""
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        tx_lines += f"• {tx['type']} — {sign}{tx['amount']:,} ت  ({tx['created_at'][:10]})\n"
    await update.message.reply_text(
        f"👛 <b>کیف پول شما</b>\n\n"
        f"💰 موجودی: <b>{_fmt(balance)}</b>\n\n"
        + (f"📋 آخرین تراکنش‌ها:\n{tx_lines}" if tx_lines else "")
        + "\nبرای شارژ روی /charge_wallet بزنید یا در منوی زیر:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


async def wallet_charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_access(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "💳 <b>شارژ کیف پول</b>\n\n"
        "مبلغ مورد نظر را به تومان وارد کنید:\n"
        "(مثال: 500000)",
        reply_markup=wallet_cancel_keyboard(),
        parse_mode="HTML",
    )
    return WALLET_ENTER_AMOUNT


async def wallet_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", "").replace("٬", "")
    if not text.isdigit() or int(text) < 10000:
        await update.message.reply_text(
            "⚠️ لطفاً یک عدد صحیح (حداقل ۱۰,۰۰۰ تومان) وارد کنید:",
            reply_markup=wallet_cancel_keyboard(),
        )
        return WALLET_ENTER_AMOUNT
    amount = int(text)
    context.user_data["wallet_charge_amount"] = amount

    card_line = f"شماره کارت: <code>{CARD_NUMBER}</code>\n" if CARD_NUMBER else ""
    owner_line = f"به نام: <b>{CARD_OWNER}</b>\n" if CARD_OWNER else ""

    await update.message.reply_text(
        f"💳 <b>اطلاعات پرداخت</b>\n\n"
        f"مبلغ: <b>{_fmt(amount)}</b>\n\n"
        f"{card_line}{owner_line}\n"
        "⚠️ <b>توجه:</b> در صورت ارسال رسید جعلی یا مغایر با واقعیت، "
        "کیف پول شما شارژ نخواهد شد و ممکن است حساب شما مسدود شود.\n\n"
        "تصویر رسید واریز را ارسال کنید:",
        parse_mode="HTML",
        reply_markup=wallet_cancel_keyboard(),
    )
    return WALLET_SEND_RECEIPT


async def wallet_charge_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً تصویر رسید را ارسال کنید:", reply_markup=wallet_cancel_keyboard())
        return WALLET_SEND_RECEIPT
    user = update.effective_user
    amount = context.user_data.get("wallet_charge_amount", 0)
    file_id = update.message.photo[-1].file_id

    charge_id = db.create_wallet_charge(user.id, amount)
    db.set_wallet_charge_receipt(charge_id, file_id)

    admin_text = (
        f"💰 <b>درخواست شارژ کیف پول</b>\n\n"
        f"👤 کاربر: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 آیدی: <code>{user.id}</code>\n"
        f"💵 مبلغ: <b>{_fmt(amount)}</b>\n"
        f"🔢 شناسه شارژ: <code>{charge_id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id, photo=file_id,
                caption=admin_text, parse_mode="HTML",
                reply_markup=admin_wallet_charge_keyboard(charge_id),
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ رسید دریافت شد و برای ادمین ارسال شد.\n"
        "پس از تأیید، موجودی کیف پول شما افزایش می‌یابد. ⏳",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def wallet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ عملیات لغو شد.")
    else:
        await update.message.reply_text("❌ عملیات لغو شد.")
    await context.bot.send_message(
        update.effective_user.id, "منوی اصلی:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(update.effective_user.id)),
    )
    return ConversationHandler.END


def wallet_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👛 کیف پول من$"), wallet_charge_start)],
        states={
            WALLET_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_charge_amount),
                CallbackQueryHandler(wallet_cancel, pattern="^cancel_wallet$"),
            ],
            WALLET_SEND_RECEIPT: [
                MessageHandler(filters.PHOTO, wallet_charge_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_charge_receipt),
                CallbackQueryHandler(wallet_cancel, pattern="^cancel_wallet$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", wallet_cancel),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), wallet_cancel),
        ],
        allow_reentry=True,
    )


# ====================================================
# ثبت آگهی فروش
# ====================================================

async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_access(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["photos"] = []
    await update.message.reply_text(
        "📢 <b>ثبت آگهی فروش</b>\n\n"
        "ابتدا نوع آگهی را انتخاب کنید:",
        reply_markup=sell_category_keyboard(),
        parse_mode="HTML",
    )
    return SELL_CATEGORY


async def sell_choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat = query.data.replace("cat_", "")
    context.user_data["category"] = cat
    cat_label = CATEGORIES.get(cat, cat)

    await query.edit_message_text(
        f"✅ دسته: <b>{cat_label}</b>\n\n"
        "مرحله ۱ — لطفاً <b>عنوان آگهی</b> را وارد کنید:\n"
        "(مثال: اکانت TH15 کامل با ۵ هیرو مکس)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_TITLE


async def sell_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ عنوان ثبت شد.\n\n"
        "مرحله ۲ — <b>توضیحات آگهی</b>:\n"
        "(آمار، لول، آیتم‌ها و جزئیات را بنویسید)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_DESCRIPTION


async def sell_receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ توضیحات ثبت شد.\n\n"
        "مرحله ۳ — <b>قیمت پایه</b> را به <b>تومان</b> وارد کنید (فقط عدد):\n"
        "(مثال: 500000)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_PRICE


async def sell_receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", "").replace("٬", "")
    if not text.isdigit() or int(text) < 1000:
        await update.message.reply_text(
            "⚠️ لطفاً یک عدد صحیح (تومان) وارد کنید:\n(مثال: 500000)",
            reply_markup=sell_cancel_keyboard(),
        )
        return SELL_PRICE
    price_toman = int(text)
    context.user_data["price_toman"] = price_toman
    buyer_pays, seller_gets, _ = db.calculate_commission(price_toman)
    await update.message.reply_text(
        f"✅ قیمت ثبت شد: <b>{_fmt(price_toman)}</b>\n\n"
        f"📊 محاسبه کارمزد:\n"
        f"• خریدار پرداخت می‌کند: <b>{_fmt(buyer_pays)}</b>\n"
        f"• سهم شما (فروشنده): <b>{_fmt(seller_gets)}</b>\n\n"
        "مرحله ۴ — تصاویر <b>اسکرین‌شات</b> را ارسال کنید. وقتی تمام شد دکمه زیر:",
        reply_markup=sell_end_photos_keyboard(),
        parse_mode="HTML",
    )
    return SELL_PHOTOS


async def sell_receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    context.user_data["photos"].append(photo.file_id)
    count = len(context.user_data["photos"])
    await update.message.reply_text(
        f"📷 تصویر {count} دریافت شد. می‌توانید بیشتر بفرستید یا پایان دهید:",
        reply_markup=sell_end_photos_keyboard(),
    )
    return SELL_PHOTOS


async def sell_end_photos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("photos"):
        await query.answer("⚠️ حداقل یک تصویر ارسال کنید!", show_alert=True)
        return SELL_PHOTOS
    await query.edit_message_text(
        "✅ تصاویر ثبت شدند.\n\n"
        "مرحله ۵ — می‌توانید یک <b>ویدیو</b> از گیم‌پلی ارسال کنید (اختیاری):",
        reply_markup=sell_skip_video_keyboard(),
        parse_mode="HTML",
    )
    return SELL_VIDEO


async def sell_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["video"] = update.message.video.file_id
    return await _sell_after_video(update, context, via_callback=False)


async def sell_skip_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["video"] = None
    return await _sell_after_video(update, context, via_callback=True)


async def _sell_after_video(update, context, via_callback: bool) -> int:
    cat = context.user_data.get("category", "coc_account")
    if cat in CLAN_CATEGORIES:
        msg = "مرحله ۶ — نام کلن را وارد کنید:"
        if via_callback:
            await update.callback_query.edit_message_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, reply_markup=sell_cancel_keyboard(), parse_mode="HTML")
        return SELL_CLAN_NAME
    else:
        msg = "مرحله ۶ — <b>ایمیل اکانت</b> را وارد کنید:"
        if via_callback:
            await update.callback_query.edit_message_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, reply_markup=sell_cancel_keyboard(), parse_mode="HTML")
        return SELL_EMAIL


# --- فیلدهای اکانت ---

async def sell_receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["email"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ ایمیل ثبت شد.\n\nمرحله ۷ — <b>رمز عبور اکانت</b>:",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_PASSWORD


async def sell_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["password"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ رمز ثبت شد.\n\nمرحله ۸ — آیا <b>ایمیل بعد از فروش تغییر کند</b>؟\n"
        "(برای امنیت خریدار توصیه می‌شود)",
        reply_markup=sell_email_change_keyboard(), parse_mode="HTML",
    )
    return SELL_EMAIL_CHANGE_Q


async def sell_email_change_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "مرحله ۸ب — <b>ایمیل جدید</b> (بعد از فروش) را وارد کنید:", parse_mode="HTML"
    )
    return SELL_NEW_EMAIL


async def sell_email_change_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["new_email"] = None
    await query.edit_message_text(
        "مرحله ۹ — <b>شماره تلفن</b> خود را وارد کنید:\n(برای ارتباط با خریدار)", parse_mode="HTML"
    )
    return SELL_PHONE


async def sell_receive_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_email"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ ایمیل جدید ثبت شد.\n\nمرحله ۹ — <b>شماره تلفن</b> خود را وارد کنید:",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_PHONE


# --- فیلدهای کلن ---

async def sell_clan_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["clan_name"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ نام کلن ثبت شد.\n\nمرحله ۷ — <b>لول کلن</b> را وارد کنید:",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_CLAN_LEVEL


async def sell_clan_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["clan_level"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ لول ثبت شد.\n\nمرحله ۸ — <b>تعداد اعضا</b>:",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_CLAN_MEMBERS


async def sell_clan_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["member_count"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ تعداد اعضا ثبت شد.\n\nمرحله ۹ — <b>تراف کلن</b> (تعداد یا رنج):",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_CLAN_TROPHIES


async def sell_clan_trophies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["clan_trophies"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ تراف ثبت شد.\n\nمرحله ۱۰ — <b>شماره تلفن</b> خود را وارد کنید:\n(برای ارتباط با خریدار)",
        reply_markup=sell_cancel_keyboard(), parse_mode="HTML",
    )
    return SELL_PHONE


# --- ثبت نهایی ---

async def sell_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    user  = update.effective_user
    ud    = context.user_data
    cat   = ud.get("category", "coc_account")
    price_toman = ud.get("price_toman")

    listing_id, unique_code = db.create_listing(
        seller_id    = user.id,
        category     = cat,
        title        = ud["title"],
        description  = ud["description"],
        price        = _fmt(price_toman) if price_toman else "",
        price_toman  = price_toman,
        email        = ud.get("email", ""),
        password     = ud.get("password", ""),
        new_email    = ud.get("new_email"),
        phone        = phone,
        clan_name    = ud.get("clan_name"),
        clan_level   = ud.get("clan_level"),
        member_count = ud.get("member_count"),
        clan_trophies= ud.get("clan_trophies"),
    )

    for fid in ud["photos"]:
        db.add_media(listing_id, "photo", fid)
    if ud.get("video"):
        db.add_media(listing_id, "video", ud["video"])

    # ارسال به ادمین برای تأیید قبل از انتشار در کانال
    cat_label  = CATEGORIES.get(cat, cat)
    buyer_pays, seller_gets, _ = db.calculate_commission(price_toman) if price_toman else (None, None, None)

    admin_caption = (
        f"🆕 <b>آگهی جدید — در انتظار تأیید</b>\n\n"
        f"📌 عنوان: {ud['title']}\n"
        f"🎮 دسته: {cat_label}\n"
        f"📝 توضیحات: {ud['description']}\n"
        f"💰 قیمت پایه: {_fmt(price_toman)}\n"
        f"🧾 خریدار می‌پردازد: {_fmt(buyer_pays)}\n"
        f"💵 سهم فروشنده: {_fmt(seller_gets)}\n"
        f"👤 فروشنده: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 آیدی فروشنده: <code>{user.id}</code>\n"
        f"🔑 کد آگهی: <code>{unique_code}</code>"
    )
    photos = ud["photos"]
    for admin_id in ADMIN_IDS:
        try:
            if photos:
                await context.bot.send_photo(
                    admin_id, photo=photos[0],
                    caption=admin_caption, parse_mode="HTML",
                    reply_markup=admin_listing_approval_keyboard(listing_id),
                )
            else:
                await context.bot.send_message(
                    admin_id, admin_caption, parse_mode="HTML",
                    reply_markup=admin_listing_approval_keyboard(listing_id),
                )
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ <b>آگهی شما ثبت شد!</b>\n\n"
        f"🔑 کد آگهی: <code>{unique_code}</code>\n\n"
        "⏳ آگهی شما برای بررسی ادمین ارسال شده است.\n"
        "پس از تأیید، در کانال منتشر می‌شود.",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
        parse_mode="HTML",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def sell_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ ثبت آگهی لغو شد.")
    else:
        await update.message.reply_text("❌ ثبت آگهی لغو شد.")
    await context.bot.send_message(
        user.id, "منوی اصلی:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    return ConversationHandler.END


def sell_conversation() -> ConversationHandler:
    cancel_cb = CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")
    text_h = lambda handler: MessageHandler(filters.TEXT & ~filters.COMMAND, handler)  # noqa: E731
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 ثبت آگهی فروش$"), sell_start)],
        states={
            SELL_CATEGORY:     [CallbackQueryHandler(sell_choose_category, pattern=r"^cat_"),
                                 cancel_cb],
            SELL_TITLE:        [text_h(sell_receive_title),        cancel_cb],
            SELL_DESCRIPTION:  [text_h(sell_receive_description),  cancel_cb],
            SELL_PRICE:        [text_h(sell_receive_price),        cancel_cb],
            SELL_PHOTOS:       [MessageHandler(filters.PHOTO, sell_receive_photo),
                                 CallbackQueryHandler(sell_end_photos_callback, pattern="^end_photos$"),
                                 cancel_cb],
            SELL_VIDEO:        [MessageHandler(filters.VIDEO, sell_receive_video),
                                 CallbackQueryHandler(sell_skip_video_callback, pattern="^skip_video$"),
                                 cancel_cb],
            SELL_EMAIL:        [text_h(sell_receive_email),        cancel_cb],
            SELL_PASSWORD:     [text_h(sell_receive_password),     cancel_cb],
            SELL_EMAIL_CHANGE_Q:[CallbackQueryHandler(sell_email_change_yes, pattern="^email_yes$"),
                                 CallbackQueryHandler(sell_email_change_no,  pattern="^email_no$"),
                                 cancel_cb],
            SELL_NEW_EMAIL:    [text_h(sell_receive_new_email),    cancel_cb],
            SELL_PHONE:        [text_h(sell_receive_phone),        cancel_cb],
            SELL_CLAN_NAME:    [text_h(sell_clan_name),            cancel_cb],
            SELL_CLAN_LEVEL:   [text_h(sell_clan_level),           cancel_cb],
            SELL_CLAN_MEMBERS: [text_h(sell_clan_members),         cancel_cb],
            SELL_CLAN_TROPHIES:[text_h(sell_clan_trophies),        cancel_cb],
        },
        fallbacks=[
            CommandHandler("cancel", sell_cancel),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), sell_cancel),
        ],
        allow_reentry=True,
    )


# ====================================================
# ادمین — تأیید/رد آگهی قبل از انتشار
# ====================================================

async def listing_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    if not listing or listing["status"] != "draft":
        await query.answer("این آگهی قبلاً پردازش شده.", show_alert=True)
        return

    ok = await _publish_listing_to_channel(context.bot, listing_id)
    if ok:
        await query.edit_message_caption(
            (query.message.caption or "") + "\n\n✅ تأیید و منتشر شد.",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                listing["seller_id"],
                f"✅ <b>آگهی شما تأیید و در کانال منتشر شد!</b>\n\n"
                f"کد آگهی: <code>{listing['unique_code']}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await query.edit_message_caption(
            (query.message.caption or "") + "\n\n⚠️ تأیید شد ولی انتشار در کانال ناموفق بود.",
            parse_mode="HTML",
        )


async def listing_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    if not listing or listing["status"] != "draft":
        await query.answer("این آگهی قبلاً پردازش شده.", show_alert=True)
        return

    db.reject_listing(listing_id)
    await query.edit_message_caption(
        (query.message.caption or "") + "\n\n❌ رد شد.",
        parse_mode="HTML",
    )
    try:
        await context.bot.send_message(
            listing["seller_id"],
            f"❌ <b>آگهی شما رد شد.</b>\n\n"
            f"عنوان: {listing['title']}\n\n"
            "لطفاً با ادمین تماس بگیرید.",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ====================================================
# خرید اکانت/کلن
# ====================================================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_access(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "🛒 <b>خرید اکانت/کلن</b>\n\n"
        "کد یکتای آگهی را وارد کنید:",
        reply_markup=wallet_cancel_keyboard(),
        parse_mode="HTML",
    )
    return BUY_ENTER_CODE


async def buy_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    user = update.effective_user
    listing = db.get_listing_by_code(code)

    if not listing or listing["status"] != "active":
        await update.message.reply_text(
            "❌ آگهی با این کد یافت نشد یا دیگر در دسترس نیست.\n"
            "کد را بررسی کنید یا دوباره امتحان کنید:"
        )
        return BUY_ENTER_CODE

    if listing["seller_id"] == user.id:
        await update.message.reply_text("⛔ شما نمی‌توانید آگهی خودتان را بخرید.")
        return BUY_ENTER_CODE

    active_tx = db.get_active_transaction_by_listing(listing["id"])
    if active_tx:
        await update.message.reply_text(
            "⚠️ این آگهی در حال حاضر در فرآیند خرید دیگری است. لطفاً بعداً امتحان کنید."
        )
        return BUY_ENTER_CODE

    price_toman = listing["price_toman"]
    if not price_toman:
        await update.message.reply_text(
            "⚠️ این آگهی قیمت عددی ندارد. لطفاً با ادمین تماس بگیرید."
        )
        return BUY_ENTER_CODE

    buyer_pays, seller_gets, bot_profit = db.calculate_commission(price_toman)
    wallet_balance = db.get_wallet_balance(user.id)
    has_enough = wallet_balance >= buyer_pays

    db.lock_listing(listing["id"])
    context.user_data["buy_listing_id"]    = listing["id"]
    context.user_data["buy_listing_title"] = listing["title"]
    context.user_data["buy_buyer_amount"]  = buyer_pays
    context.user_data["buy_seller_amount"] = seller_gets
    context.user_data["buy_price_toman"]   = price_toman
    context.user_data["wallet_balance"]    = wallet_balance

    cat_label  = CATEGORIES.get(listing["category"], listing["category"])

    await update.message.reply_text(
        f"✅ آگهی پیدا شد!\n\n"
        f"🎮 <b>{listing['title']}</b>  [{cat_label}]\n"
        f"📝 {listing['description']}\n\n"
        f"💰 قیمت پایه: {_fmt(price_toman)}\n"
        f"🧾 <b>مبلغ نهایی شما (با کارمزد ۱۰٪): {_fmt(buyer_pays)}</b>\n\n"
        "روش پرداخت را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=buy_payment_method_keyboard(has_enough, buyer_pays, wallet_balance),
    )
    return BUY_PAYMENT_METHOD


async def buy_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    buyer_pays = context.user_data.get("buy_buyer_amount", 0)
    card_line  = f"شماره کارت: <code>{CARD_NUMBER}</code>\n" if CARD_NUMBER else ""
    owner_line = f"به نام: <b>{CARD_OWNER}</b>\n" if CARD_OWNER else ""

    await query.edit_message_text(
        f"💳 <b>پرداخت با کارت بانکی</b>\n\n"
        f"مبلغ: <b>{_fmt(buyer_pays)}</b>\n\n"
        f"{card_line}{owner_line}\n"
        "⚠️ <b>هشدار:</b> ارسال رسید جعلی = مسدود شدن دائمی + عدم تحویل\n\n"
        "تصویر رسید واریز را ارسال کنید:",
        parse_mode="HTML",
    )
    return BUY_SEND_RECEIPT


async def buy_payment_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    listing_id   = context.user_data.get("buy_listing_id")
    buyer_amount = context.user_data.get("buy_buyer_amount", 0)
    seller_amount= context.user_data.get("buy_seller_amount", 0)
    listing_title= context.user_data.get("buy_listing_title", "")

    listing = db.get_listing_by_id(listing_id)
    if not listing:
        await query.edit_message_text("❌ خطا رخ داد. دوباره امتحان کنید.")
        return ConversationHandler.END

    # کسر اتمیک از کیف پول
    ok = db.debit_wallet_atomic(
        user.id, buyer_amount, "purchase",
        note=f"خرید آگهی {listing['unique_code']}",
    )
    if not ok:
        await query.edit_message_text(
            "❌ موجودی کیف پول کافی نیست.\n\n"
            f"موجودی شما: {_fmt(db.get_wallet_balance(user.id))}\n"
            f"مبلغ مورد نیاز: {_fmt(buyer_amount)}\n\n"
            "ابتدا کیف پول خود را شارژ کنید.",
        )
        db.unlock_listing(listing_id)
        context.user_data.clear()
        return ConversationHandler.END

    # تراکنش مستقیم به pending_seller (بدون نیاز به تأیید ادمین)
    tx_id = db.create_transaction(
        listing_id, user.id,
        payment_method="wallet",
        buyer_amount=buyer_amount,
        seller_amount=seller_amount,
    )

    # اطلاع به فروشنده
    try:
        await context.bot.send_message(
            listing["seller_id"],
            f"✅ <b>پرداخت از کیف پول خریدار تأیید شد!</b>\n\n"
            f"🛒 آگهی: <b>{listing['title']}</b>\n"
            f"💵 سهم شما: <b>{_fmt(seller_amount)}</b>\n\n"
            f"شما <b>{SELLER_CONFIRM_TIMEOUT_HOURS} ساعت</b> فرصت دارید تحویل اکانت را تأیید کنید:",
            reply_markup=seller_confirm_keyboard(tx_id),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.edit_message_text(
        f"✅ <b>خرید موفق!</b>\n\n"
        f"مبلغ <b>{_fmt(buyer_amount)}</b> از کیف پول شما کسر شد.\n"
        "فروشنده مطلع شد و باید اکانت را تحویل دهد. ⏳",
        parse_mode="HTML",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def buy_wallet_insufficient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer(
        "موجودی کافی نیست! ابتدا کیف پول خود را شارژ کنید.", show_alert=True
    )
    return BUY_PAYMENT_METHOD


async def buy_receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً تصویر رسید را ارسال کنید (نه متن):")
        return BUY_SEND_RECEIPT

    photo_file_id = update.message.photo[-1].file_id
    listing_id    = context.user_data.get("buy_listing_id")
    listing_title = context.user_data.get("buy_listing_title", "نامشخص")
    buyer_amount  = context.user_data.get("buy_buyer_amount", 0)
    seller_amount = context.user_data.get("buy_seller_amount", 0)
    user = update.effective_user

    tx_id = db.create_transaction(
        listing_id, user.id,
        payment_method="card",
        buyer_amount=buyer_amount,
        seller_amount=seller_amount,
    )
    db.set_receipt(tx_id, photo_file_id)

    admin_text = (
        f"🧾 <b>رسید پرداخت جدید</b>\n\n"
        f"🛒 آگهی: <b>{listing_title}</b>\n"
        f"💰 مبلغ: <b>{_fmt(buyer_amount)}</b>\n"
        f"👤 خریدار: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 آیدی: <code>{user.id}</code>\n"
        f"🔢 شناسه تراکنش: <code>{tx_id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id, photo=photo_file_id,
                caption=admin_text, parse_mode="HTML",
                reply_markup=admin_receipt_keyboard(tx_id),
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ رسید دریافت شد و برای ادمین ارسال شد.\nپس از تأیید اطلاع‌رسانی می‌شود. ⏳",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def buy_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    listing_id = context.user_data.get("buy_listing_id")
    if listing_id:
        db.unlock_listing(listing_id)
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ فرآیند خرید لغو شد.")
    else:
        await update.message.reply_text("❌ فرآیند خرید لغو شد.")
    await context.bot.send_message(
        user.id, "منوی اصلی:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    return ConversationHandler.END


def buy_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 خرید اکانت/کلن$"), buy_start)],
        states={
            BUY_ENTER_CODE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_receive_code)],
            BUY_PAYMENT_METHOD: [
                CallbackQueryHandler(buy_payment_card,         pattern="^pay_card$"),
                CallbackQueryHandler(buy_payment_wallet,       pattern="^pay_wallet$"),
                CallbackQueryHandler(buy_wallet_insufficient,  pattern="^wallet_insufficient$"),
                CallbackQueryHandler(buy_cancel,               pattern="^cancel_buy$"),
            ],
            BUY_SEND_RECEIPT: [
                MessageHandler(filters.PHOTO, buy_receive_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_receive_receipt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", buy_cancel),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), buy_cancel),
        ],
        allow_reentry=True,
    )


# ====================================================
# Callback های ادمین — تأیید/رد رسید
# ====================================================

async def admin_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    tx_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(tx_id)
    if not tx:
        await query.edit_message_caption("❌ تراکنش یافت نشد.")
        return
    if tx["status"] != "pending_admin":
        await query.answer("این تراکنش قبلاً بررسی شده.", show_alert=True)
        return

    db.admin_approve_transaction(tx_id)
    listing = db.get_listing_by_id(tx["listing_id"])
    seller_amount = tx["seller_amount"]

    try:
        await context.bot.send_message(
            listing["seller_id"],
            f"✅ <b>پرداخت تأیید شد!</b>\n\n"
            f"🛒 آگهی: <b>{listing['title']}</b>\n"
            f"💵 سهم شما: <b>{_fmt(seller_amount)}</b>\n\n"
            f"شما <b>{SELLER_CONFIRM_TIMEOUT_HOURS} ساعت</b> فرصت دارید تحویل اکانت را تأیید کنید:",
            reply_markup=seller_confirm_keyboard(tx_id),
            parse_mode="HTML",
        )
    except Exception:
        pass

    admin = update.effective_user
    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n✅ تأیید شد توسط {admin.full_name}",
        parse_mode="HTML",
    )


async def admin_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    tx_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(tx_id)
    if not tx or tx["status"] != "pending_admin":
        await query.answer("این تراکنش قبلاً بررسی شده.", show_alert=True)
        return

    db.admin_reject_transaction(tx_id)
    listing = db.get_listing_by_id(tx["listing_id"])
    if listing:
        db.unlock_listing(listing["id"])

    try:
        await context.bot.send_message(
            tx["buyer_id"],
            "❌ <b>رسید پرداخت شما رد شد.</b>\n\n"
            "رسید معتبر نبود یا مبلغ اشتباه بود. برای پیگیری با ادمین تماس بگیرید.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    admin = update.effective_user
    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n❌ رد شد توسط {admin.full_name}",
        parse_mode="HTML",
    )


# ====================================================
# ادمین — تأیید/رد شارژ کیف پول
# ====================================================

async def wcharge_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    charge_id = int(query.data.split("_")[-1])
    result = db.approve_wallet_charge(charge_id)
    if result is None:
        await query.answer("این شارژ قبلاً پردازش شده.", show_alert=True)
        return
    user_id, amount = result
    try:
        await context.bot.send_message(
            user_id,
            f"✅ <b>کیف پول شارژ شد!</b>\n\n"
            f"💰 مبلغ: <b>{_fmt(amount)}</b> به موجودی شما اضافه شد.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n✅ تأیید شد — {_fmt(amount)} شارژ شد.",
        parse_mode="HTML",
    )


async def wcharge_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    charge_id = int(query.data.split("_")[-1])
    user_id = db.reject_wallet_charge(charge_id)
    if user_id is None:
        await query.answer("این شارژ قبلاً پردازش شده.", show_alert=True)
        return
    try:
        await context.bot.send_message(
            user_id,
            "❌ <b>درخواست شارژ کیف پول رد شد.</b>\n\n"
            "رسید معتبر نبود. برای پیگیری با ادمین تماس بگیرید.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await query.edit_message_caption(
        (query.message.caption or "") + "\n\n❌ رد شد.",
        parse_mode="HTML",
    )


# ====================================================
# Callback تأیید تحویل فروشنده
# ====================================================

async def seller_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    tx_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(tx_id)
    if not tx:
        await query.edit_message_text("❌ تراکنش یافت نشد.")
        return
    listing = db.get_listing_by_id(tx["listing_id"])
    if not listing or listing["seller_id"] != user.id:
        await query.answer("⛔ این تراکنش متعلق به شما نیست!", show_alert=True)
        return
    if tx["status"] != "pending_seller":
        await query.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    db.seller_confirm_transaction(tx_id)
    db.deactivate_listing(listing["id"])

    buyer_text = (
        f"🎉 <b>فروشنده اکانت را تحویل داد!</b>\n\n"
        f"🎮 <b>{listing['title']}</b>\n\n"
    )
    if listing["category"] in CLAN_CATEGORIES:
        if listing["clan_name"]:    buyer_text += f"🏰 نام کلن: <b>{listing['clan_name']}</b>\n"
        if listing["clan_level"]:   buyer_text += f"🎖 لول: {listing['clan_level']}\n"
        if listing["member_count"]: buyer_text += f"👥 اعضا: {listing['member_count']}\n"
        if listing["clan_trophies"]:buyer_text += f"🏆 تراف: {listing['clan_trophies']}\n"
    else:
        buyer_text += (
            f"📧 ایمیل: <code>{listing['email']}</code>\n"
            f"🔑 رمز عبور: <code>{listing['password']}</code>\n"
        )
        if listing["new_email"]:
            buyer_text += f"📨 ایمیل جدید (بعد از تحویل): <code>{listing['new_email']}</code>\n"

    seller_id = listing["seller_id"]
    buyer_text += (
        f"\n📞 تماس با فروشنده:\n<a href='tg://user?id={seller_id}'>کلیک کنید</a>\n\n"
        "پس از بررسی اکانت، یکی از گزینه‌های زیر را انتخاب کنید:"
    )

    try:
        await context.bot.send_message(
            tx["buyer_id"], buyer_text,
            parse_mode="HTML",
            reply_markup=buyer_confirm_keyboard(tx_id),
        )
    except Exception:
        pass

    buyer_id = tx["buyer_id"]
    await query.edit_message_text(
        "✅ <b>تحویل اکانت تأیید شد!</b>\n\n"
        "اطلاعات به خریدار ارسال شد. منتظر تأیید دریافت از ایشان هستیم.\n"
        f"📞 تماس با خریدار:\n<a href='tg://user?id={buyer_id}'>کلیک کنید</a>",
        parse_mode="HTML",
    )


# ====================================================
# Callback تأیید / اعتراض خریدار
# ====================================================

async def buyer_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    tx_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(tx_id)
    if not tx:
        await query.edit_message_text("❌ تراکنش یافت نشد.")
        return
    if tx["buyer_id"] != user.id:
        await query.answer("⛔ این تراکنش متعلق به شما نیست!", show_alert=True)
        return
    if tx["status"] != "pending_buyer":
        await query.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    listing = db.get_listing_by_id(tx["listing_id"])
    db.buyer_confirm_transaction(tx_id)
    db.mark_listing_sold(tx["listing_id"])

    # حذف آگهی از کانال
    if listing and listing["channel_msg_id"]:
        try:
            await context.bot.delete_message(CHANNEL_ID, listing["channel_msg_id"])
        except Exception:
            pass

    # اطلاع به فروشنده
    if listing:
        try:
            await context.bot.send_message(
                listing["seller_id"],
                f"🎉 <b>خریدار دریافت اکانت را تأیید کرد!</b>\n\n"
                f"🎮 آگهی: <b>{listing['title']}</b>\n"
                f"💵 سهم شما: <b>{_fmt(tx['seller_amount'])}</b>\n"
                "معامله تکمیل شد. ✅",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await query.edit_message_text(
        "✅ <b>دریافت اکانت تأیید شد!</b>\n\nمعامله با موفقیت تکمیل شد. ممنون از خرید شما! 🎉",
        parse_mode="HTML",
    )


async def buyer_dispute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    tx_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(tx_id)
    if not tx:
        await query.edit_message_text("❌ تراکنش یافت نشد.")
        return
    if tx["buyer_id"] != user.id:
        await query.answer("⛔ این تراکنش متعلق به شما نیست!", show_alert=True)
        return
    if tx["status"] != "pending_buyer":
        await query.answer("این تراکنش قبلاً پردازش شده.", show_alert=True)
        return

    listing = db.get_listing_by_id(tx["listing_id"])
    title = listing["title"] if listing else "نامشخص"

    await _notify_admins(
        context.bot,
        f"⚠️ <b>اعتراض خریدار</b>\n\n"
        f"🛒 آگهی: <b>{title}</b>\n"
        f"👤 خریدار: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 آیدی: <code>{user.id}</code>\n"
        f"🔢 تراکنش: <code>{tx_id}</code>\n\n"
        "خریدار مشکل گزارش کرده است. لطفاً میانجی‌گری کنید.",
        parse_mode="HTML",
    )
    await query.edit_message_text(
        "⚠️ <b>اعتراض شما ثبت شد.</b>\n\n"
        "موضوع به ادمین ارجاع داده شد. به زودی با شما تماس گرفته می‌شود. ⏳",
        parse_mode="HTML",
    )


# ====================================================
# هندلرهای آگهی‌های من
# ====================================================

async def my_listings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_access(update, context):
        return
    user = update.effective_user
    listings = db.get_seller_listings(user.id)
    if not listings:
        await update.message.reply_text(
            "📋 شما هیچ آگهی‌ای ندارید.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
        )
        return
    await update.message.reply_text(
        f"📋 <b>آگهی‌های شما ({len(listings)} آگهی):</b>",
        reply_markup=my_listings_keyboard(listings),
        parse_mode="HTML",
    )


async def view_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    user = update.effective_user
    if not listing or listing["seller_id"] != user.id:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return
    status = STATUS_FA.get(listing["status"], listing["status"])
    cat    = CATEGORIES.get(listing["category"], listing["category"])
    price_line = f"💰 قیمت: {_fmt(listing['price_toman'])}\n" if listing.get("price_toman") else ""
    text = (
        f"📋 <b>جزئیات آگهی</b>\n\n"
        f"📌 عنوان: {listing['title']}\n"
        f"🎮 دسته: {cat}\n"
        f"📝 توضیحات: {listing['description']}\n"
        f"{price_line}"
        f"🔑 کد: <code>{listing['unique_code']}</code>\n"
        f"📊 وضعیت: {status}"
    )
    await query.edit_message_text(text, parse_mode="HTML",
                                   reply_markup=listing_actions_keyboard(listing_id, listing["status"]))


async def delete_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    user = update.effective_user
    if not listing or listing["seller_id"] != user.id:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return
    db.deactivate_listing(listing_id)
    if listing["channel_msg_id"]:
        try:
            await context.bot.delete_message(CHANNEL_ID, listing["channel_msg_id"])
        except Exception:
            pass
    await query.edit_message_text("🗑 آگهی حذف شد.")


async def my_listings_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    listings = db.get_seller_listings(update.effective_user.id)
    await query.edit_message_text(
        f"📋 <b>آگهی‌های شما ({len(listings)} آگهی):</b>",
        reply_markup=my_listings_keyboard(listings),
        parse_mode="HTML",
    )


# ====================================================
# پنل ادمین
# ====================================================

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("⚙️ پنل مدیریت:", reply_markup=admin_panel_keyboard())


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_main_menu(update, context)


async def list_banned_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    users = db.get_banned_users()
    if not users:
        await update.message.reply_text("✅ هیچ کاربر مسدودی وجود ندارد.")
        return
    lines = []
    for u in users[:30]:
        uname = f"@{u['username']}" if u["username"] else "بدون یوزرنیم"
        lines.append(f"• {u['full_name']} ({uname}) — <code>{u['user_id']}</code>\n  دلیل: {u['ban_reason'] or '—'}")
    await update.message.reply_text(
        "🚫 <b>کاربران مسدود:</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML",
    )


async def unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("آیدی عددی تلگرام کاربر را وارد کنید:")
    return ADMIN_WAIT_UNBAN_ID


async def unban_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ فقط عدد وارد کنید:")
        return ADMIN_WAIT_UNBAN_ID
    user_id = int(text)
    user_row = db.get_user(user_id)
    if not user_row:
        await update.message.reply_text("❌ کاربر یافت نشد.")
        return ConversationHandler.END
    db.unban_user(user_id)
    await update.message.reply_text(
        f"✅ کاربر <code>{user_id}</code> رفع مسدودیت شد.",
        parse_mode="HTML",
        reply_markup=admin_panel_keyboard(),
    )
    try:
        await context.bot.send_message(user_id, "✅ مسدودیت شما برداشته شد. می‌توانید از ربات استفاده کنید.")
    except Exception:
        pass
    return ConversationHandler.END


async def admin_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("کد یکتای آگهی را وارد کنید:")
    return ADMIN_WAIT_SEARCH_CODE


async def admin_search_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    listing = db.get_listing_by_code(code)
    if not listing:
        await update.message.reply_text("❌ آگهی یافت نشد.")
        return ConversationHandler.END
    cat = CATEGORIES.get(listing["category"], listing["category"])
    status = STATUS_FA.get(listing["status"], listing["status"])
    price_line = f"💰 قیمت: {_fmt(listing['price_toman'])}\n" if listing.get("price_toman") else ""
    text = (
        f"📋 <b>نتیجه جستجو</b>\n\n"
        f"📌 عنوان: {listing['title']}\n"
        f"🎮 دسته: {cat}\n"
        f"📝 توضیحات: {listing['description']}\n"
        f"{price_line}"
        f"🔑 کد: <code>{listing['unique_code']}</code>\n"
        f"📊 وضعیت: {status}\n"
        f"👤 فروشنده: <code>{listing['seller_id']}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_panel_keyboard())
    return ConversationHandler.END


async def admin_listings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("📋 فیلتر آگهی‌ها:", reply_markup=admin_listings_filter_keyboard())


async def admin_listings_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data  # admin_listings_active / admin_listings_all / ...
    if data == "admin_listings_back":
        await query.edit_message_text("📋 فیلتر آگهی‌ها:", reply_markup=admin_listings_filter_keyboard())
        return
    status_map = {
        "admin_listings_active":   "active",
        "admin_listings_reserved": "reserved",
        "admin_listings_inactive": "inactive",
        "admin_listings_sold":     "sold",
        "admin_listings_draft":    "draft",
        "admin_listings_all":      None,
    }
    status_filter = status_map.get(data)
    listings = db.get_all_listings(status_filter)
    if not listings:
        await query.edit_message_text("هیچ آگهی‌ای یافت نشد.", reply_markup=admin_listings_filter_keyboard())
        return
    await query.edit_message_text(
        f"📋 {len(listings)} آگهی یافت شد:",
        reply_markup=admin_listings_keyboard(listings),
    )


async def admin_view_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    if not listing:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return
    status = STATUS_FA.get(listing["status"], listing["status"])
    cat    = CATEGORIES.get(listing["category"], listing["category"])
    price_line = f"💰 قیمت: {_fmt(listing['price_toman'])}\n" if listing.get("price_toman") else ""
    buyer_pays, seller_gets, bot_profit = (
        db.calculate_commission(listing["price_toman"]) if listing.get("price_toman") else (None, None, None)
    )
    commission_line = (
        f"🧾 خریدار می‌پردازد: {_fmt(buyer_pays)}\n"
        f"💵 سهم فروشنده: {_fmt(seller_gets)}\n"
        f"💹 سود ربات: {_fmt(bot_profit)}\n"
    ) if buyer_pays else ""

    text = (
        f"📋 <b>جزئیات آگهی</b>\n\n"
        f"📌 {listing['title']}\n"
        f"🎮 دسته: {cat}\n"
        f"📝 {listing['description']}\n"
        f"{price_line}{commission_line}"
        f"🔑 کد: <code>{listing['unique_code']}</code>\n"
        f"📊 وضعیت: {status}\n"
        f"👤 فروشنده: <code>{listing['seller_id']}</code>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=admin_listing_actions_keyboard(listing_id, listing["status"]),
    )


async def admin_deactivate_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    if not listing:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return

    db.deactivate_listing(listing_id)

    # حذف از کانال
    deleted_from_channel = False
    if listing["channel_msg_id"]:
        try:
            await context.bot.delete_message(CHANNEL_ID, listing["channel_msg_id"])
            deleted_from_channel = True
        except Exception:
            pass

    channel_note = " و از کانال حذف شد" if deleted_from_channel else " (حذف از کانال ناموفق بود)"
    await query.edit_message_text(
        f"🗑 آگهی «{listing['title']}» غیرفعال شد{channel_note}.",
        reply_markup=admin_listings_filter_keyboard(),
    )


# ====================================================
# گزارش مالی ادمین
# ====================================================

async def admin_financial_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_IDS:
        return
    stats = db.get_financial_summary()
    text = (
        f"💰 <b>گزارش مالی ربات</b>\n\n"
        f"📦 معاملات تکمیل‌شده: <b>{stats['completed_count']}</b>\n"
        f"💳 جمع دریافتی از خریداران: <b>{_fmt(stats['total_buyer_paid'])}</b>\n"
        f"💵 جمع پرداختی به فروشندگان: <b>{_fmt(stats['total_seller_got'])}</b>\n"
        f"💹 <b>سود خالص ربات: {_fmt(stats['bot_profit'])}</b>\n\n"
        f"👛 شارژهای کیف پول در انتظار: {stats['pending_charges_count']} ({_fmt(stats['pending_charges_sum'])})\n"
        f"✅ شارژهای تأیید‌شده: {stats['approved_charges_count']} ({_fmt(stats['approved_charges_sum'])})"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_panel_keyboard())


def admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✅ رفع مسدودیت کاربر$"), unban_start),
            MessageHandler(filters.Regex("^🔍 جستجوی آگهی$"), admin_search_start),
        ],
        states={
            ADMIN_WAIT_UNBAN_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, unban_receive_id)],
            ADMIN_WAIT_SEARCH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_receive_code)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), back_to_main)],
        allow_reentry=True,
    )


# ====================================================
# Job های دوره‌ای — Timeout ها
# ====================================================

async def check_seller_timeouts(context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending_seller_transactions()
    now = datetime.now(tz=timezone.utc)
    for tx in pending:
        approved_at_str = tx["admin_approved_at"]
        if not approved_at_str:
            continue
        try:
            approved_at = datetime.fromisoformat(approved_at_str).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if now - approved_at < timedelta(hours=SELLER_CONFIRM_TIMEOUT_HOURS):
            continue
        listing = db.get_listing_by_id(tx["listing_id"])
        if not listing:
            continue
        db.ban_user(listing["seller_id"],
                    reason=f"عدم تأیید تحویل اکانت در {SELLER_CONFIRM_TIMEOUT_HOURS}ساعت (تراکنش {tx['id']})")
        db.deactivate_listing(listing["id"])
        db.timeout_transaction(tx["id"])
        try:
            await context.bot.send_message(
                tx["buyer_id"],
                f"⚠️ فروشنده در مهلت {SELLER_CONFIRM_TIMEOUT_HOURS} ساعته تأیید نکرد.\n"
                "فروشنده مسدود شد. با ادمین تماس بگیرید.",
            )
        except Exception:
            pass
        await _notify_admins(
            context.bot,
            f"🚨 <b>Timeout فروشنده</b>\n"
            f"آگهی: {listing['title']}\n"
            f"فروشنده: <code>{listing['seller_id']}</code>\n"
            f"تراکنش: <code>{tx['id']}</code>",
            parse_mode="HTML",
        )
        logger.info("Seller %s timed out — tx %s.", listing["seller_id"], tx["id"])


async def check_buyer_timeouts(context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = db.get_pending_buyer_transactions()
    now = datetime.now(tz=timezone.utc)
    for tx in pending:
        confirmed_str = tx["seller_confirmed_at"]
        if not confirmed_str:
            continue
        try:
            confirmed_at = datetime.fromisoformat(confirmed_str).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if now - confirmed_at < timedelta(hours=BUYER_CONFIRM_TIMEOUT_HOURS):
            continue
        listing = db.get_listing_by_id(tx["listing_id"])
        db.buyer_confirm_transaction(tx["id"])
        db.mark_listing_sold(tx["listing_id"])
        if listing and listing["channel_msg_id"]:
            try:
                await context.bot.delete_message(CHANNEL_ID, listing["channel_msg_id"])
            except Exception:
                pass
        try:
            await context.bot.send_message(
                tx["buyer_id"],
                f"ℹ️ چون در مهلت {BUYER_CONFIRM_TIMEOUT_HOURS} ساعته پاسخی ندادید، "
                "سفارش به‌صورت خودکار تکمیل‌شده در نظر گرفته شد.",
            )
        except Exception:
            pass
        if listing:
            try:
                await context.bot.send_message(
                    listing["seller_id"],
                    f"✅ سفارش «{listing['title']}» به‌صورت خودکار تکمیل شد.",
                )
            except Exception:
                pass
        logger.info("Buyer timeout auto-complete — tx %s.", tx["id"])


# ====================================================
# Self-ping job
# ====================================================

async def self_ping_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not RENDER_EXTERNAL_URL:
        return
    url = RENDER_EXTERNAL_URL.rstrip("/") + "/"
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "TelegramBot-SelfPing/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.debug("Self-ping → %s  status=%d", url, resp.status)
    except Exception as exc:
        logger.warning("Self-ping failed: %s", exc)


# ====================================================
# راه‌اندازی اصلی
# ====================================================

def main() -> None:
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    db.init_db()
    logger.info("دیتابیس راه‌اندازی شد.")

    health_thread = threading.Thread(target=_start_health_server, daemon=True)
    health_thread.start()

    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start و عضویت
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"))
    app.add_handler(CallbackQueryHandler(accept_warning_callback,   pattern="^accept_warning$"))

    # مکالمه‌ها
    app.add_handler(sell_conversation())
    app.add_handler(buy_conversation())
    app.add_handler(wallet_conversation())
    app.add_handler(admin_conversation())

    # منو
    app.add_handler(MessageHandler(filters.Regex("^⚙️ پنل مدیریت$"),          admin_panel_handler))
    app.add_handler(MessageHandler(filters.Regex("^🚫 لیست کاربران مسدود$"),  list_banned_handler))
    app.add_handler(MessageHandler(filters.Regex("^📋 مدیریت آگهی‌ها$"),      admin_listings_handler))
    app.add_handler(MessageHandler(filters.Regex("^💰 گزارش مالی$"),           admin_financial_handler))
    app.add_handler(MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^📋 آگهی‌های من$"),          my_listings_handler))
    app.add_handler(MessageHandler(filters.Regex("^👛 کیف پول من$"),           wallet_handler))
    app.add_handler(MessageHandler(filters.Regex("^🔗 دعوت از دوستان$"),      referral_handler))

    # Callback — آگهی (ادمین: تأیید/رد قبل از انتشار)
    app.add_handler(CallbackQueryHandler(listing_approve_callback, pattern=r"^listing_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(listing_reject_callback,  pattern=r"^listing_reject_\d+$"))

    # Callback — رسید پرداخت
    app.add_handler(CallbackQueryHandler(admin_approve_callback, pattern=r"^admin_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_reject_callback,  pattern=r"^admin_reject_\d+$"))

    # Callback — شارژ کیف پول
    app.add_handler(CallbackQueryHandler(wcharge_approve_callback, pattern=r"^wcharge_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(wcharge_reject_callback,  pattern=r"^wcharge_reject_\d+$"))

    # Callback — فروشنده/خریدار
    app.add_handler(CallbackQueryHandler(seller_confirm_callback, pattern=r"^seller_confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(buyer_confirm_callback,  pattern=r"^buyer_confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(buyer_dispute_callback,  pattern=r"^buyer_dispute_\d+$"))

    # Callback — آگهی‌های من
    app.add_handler(CallbackQueryHandler(view_listing_callback,      pattern=r"^view_listing_\d+$"))
    app.add_handler(CallbackQueryHandler(delete_listing_callback,    pattern=r"^delete_listing_\d+$"))
    app.add_handler(CallbackQueryHandler(my_listings_back_callback,  pattern="^my_listings_back$"))

    # Callback — ادمین مدیریت آگهی‌ها
    app.add_handler(CallbackQueryHandler(admin_listings_filter_callback,    pattern=r"^admin_listings_"))
    app.add_handler(CallbackQueryHandler(admin_view_listing_callback,       pattern=r"^admin_view_listing_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_deactivate_listing_callback, pattern=r"^admin_deactivate_\d+$"))

    # Job ها
    app.job_queue.run_repeating(check_seller_timeouts, interval=TIMEOUT_CHECK_INTERVAL_MINUTES * 60, first=60)
    app.job_queue.run_repeating(check_buyer_timeouts,  interval=TIMEOUT_CHECK_INTERVAL_MINUTES * 60, first=120)

    if RENDER_EXTERNAL_URL:
        app.job_queue.run_repeating(self_ping_job, interval=10 * 60, first=30)
        logger.info("Self-ping registered → %s", RENDER_EXTERNAL_URL)

    logger.info("ربات شروع به کار کرد (Polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
