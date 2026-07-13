# -*- coding: utf-8 -*-
"""ربات واسطه خرید و فروش اکانت بازی — نقطه ورود اصلی"""
import logging
from datetime import datetime, timezone, timedelta

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
    CARD_NUMBER,
    CARD_OWNER,
    CHANNEL_ID,
    CHANNEL_LINK,
    SELLER_CONFIRM_TIMEOUT_HOURS,
    TIMEOUT_CHECK_INTERVAL_MINUTES,
)
from keyboards import (
    admin_panel_keyboard,
    admin_receipt_keyboard,
    channel_join_keyboard,
    listing_actions_keyboard,
    main_menu_keyboard,
    my_listings_keyboard,
    sell_cancel_keyboard,
    sell_email_change_keyboard,
    sell_end_photos_keyboard,
    sell_skip_video_keyboard,
    seller_confirm_keyboard,
    warning_keyboard,
)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===========================
# شماره مراحل مکالمه فروش
# ===========================
(
    SELL_TITLE,
    SELL_DESCRIPTION,
    SELL_PHOTOS,
    SELL_VIDEO,
    SELL_EMAIL,
    SELL_PASSWORD,
    SELL_EMAIL_CHANGE_Q,
    SELL_NEW_EMAIL,
    SELL_PHONE,
) = range(9)

# مراحل مکالمه خرید
BUY_ENTER_CODE, BUY_SEND_RECEIPT = range(9, 11)

# مراحل مکالمه ادمین
ADMIN_WAIT_UNBAN_ID = 11

# وضعیت فارسی آگهی
STATUS_FA = {
    "active":   "🟢 فعال",
    "reserved": "🟡 در حال خرید",
    "inactive": "🔴 غیرفعال",
    "sold":     "✅ فروخته شده",
}


# ====================================================
# توابع کمکی مشترک
# ====================================================

async def is_member(bot: Bot, user_id: int) -> bool:
    """بررسی عضویت کاربر در کانال."""
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError:
        return False


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    بررسی مسدودی + عضویت کانال + هشدار اولیه.
    True  = کاربر مجاز است.
    False = پیامی ارسال شد؛ هندلر باید برگردد.
    """
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


async def send_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str = "منوی اصلی:",
) -> None:
    user_id = update.effective_user.id
    await update.effective_message.reply_text(
        text,
        reply_markup=main_menu_keyboard(is_admin=is_admin(user_id)),
    )


# ====================================================
# هندلرهای /start و عضویت
# ====================================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.full_name)

    if db.is_banned(user.id):
        await update.message.reply_text(
            "⛔ دسترسی شما به ربات مسدود شده است.\n"
            "در صورت اعتراض با ادمین تماس بگیرید."
        )
        return

    if not await is_member(context.bot, user.id):
        await update.message.reply_text(
            "👋 سلام!\n\n"
            "📢 برای استفاده از ربات باید عضو کانال ما باشید.\n"
            "پس از عضویت روی «بررسی مجدد» بزنید:",
            reply_markup=channel_join_keyboard(CHANNEL_LINK),
        )
        return

    user_row = db.get_user(user.id)
    if user_row and not user_row["warned"]:
        await update.message.reply_text(
            "⚠️ <b>هشدار مهم</b>\n\n"
            "در صورتی که مشخص شود قصد کلاهبرداری دارید یا اطلاعات نادرست ارائه می‌دهید، "
            "دسترسی شما برای همیشه مسدود می‌شود و مشخصات شما در اختیار سایر کاربران "
            "قرار می‌گیرد.\n\n"
            "برای ادامه استفاده از ربات تأیید کنید:",
            reply_markup=warning_keyboard(),
            parse_mode="HTML",
        )
        return

    await send_main_menu(
        update, context,
        f"👋 سلام {user.first_name}!\nبه ربات واسطه خرید و فروش اکانت خوش آمدید:",
    )


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
            "در صورتی که مشخص شود قصد کلاهبرداری دارید یا اطلاعات نادرست ارائه می‌دهید، "
            "دسترسی شما برای همیشه مسدود می‌شود و مشخصات شما در اختیار سایر کاربران "
            "قرار می‌گیرد.\n\n"
            "برای ادامه استفاده از ربات تأیید کنید:",
            reply_markup=warning_keyboard(),
            parse_mode="HTML",
        )
        return

    await query.edit_message_text("✅ عضویت تأیید شد!")
    await context.bot.send_message(
        user.id,
        f"👋 سلام {user.first_name}!\nبه ربات واسطه خرید و فروش اکانت خوش آمدید:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


async def accept_warning_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    db.set_warned(user.id)
    await query.edit_message_text("✅ با موفقیت تأیید شد. خوش آمدید!")
    await context.bot.send_message(
        user.id,
        f"👋 سلام {user.first_name}!\nبه ربات واسطه خرید و فروش اکانت خوش آمدید:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )


# ====================================================
# هندلرهای ثبت آگهی فروش
# ====================================================

async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_access(update, context):
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["photos"] = []
    context.user_data["video"] = None

    await update.message.reply_text(
        "📢 <b>ثبت آگهی فروش اکانت</b>\n\n"
        "مرحله ۱/۸ — لطفاً <b>عنوان آگهی</b> را وارد کنید:\n"
        "(مثال: اکانت کلش آف کلنز تاون ۱۵)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_TITLE


async def sell_receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ عنوان ثبت شد.\n\n"
        "مرحله ۲/۸ — لطفاً <b>توضیحات آگهی</b> را بنویسید:\n"
        "(آمار، لول، آیتم‌ها و جزئیات اکانت را ذکر کنید)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_DESCRIPTION


async def sell_receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ توضیحات ثبت شد.\n\n"
        "مرحله ۳/۸ — لطفاً <b>تصاویر اسکرین‌شات</b> اکانت را ارسال کنید.\n"
        "می‌توانید چند تصویر بفرستید. وقتی تمام شد روی دکمه زیر بزنید:",
        reply_markup=sell_end_photos_keyboard(),
        parse_mode="HTML",
    )
    return SELL_PHOTOS


async def sell_receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    context.user_data["photos"].append(photo.file_id)
    count = len(context.user_data["photos"])
    await update.message.reply_text(
        f"📷 تصویر {count} دریافت شد. می‌توانید تصویر بیشتری بفرستید یا پایان دهید:",
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
        "مرحله ۴/۸ — می‌توانید یک <b>ویدیو</b> از گیم‌پلی اکانت ارسال کنید (اختیاری):",
        reply_markup=sell_skip_video_keyboard(),
        parse_mode="HTML",
    )
    return SELL_VIDEO


async def sell_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["video"] = update.message.video.file_id
    await update.message.reply_text(
        "✅ ویدیو دریافت شد.\n\n"
        "مرحله ۵/۸ — لطفاً <b>ایمیل اکانت</b> را وارد کنید:",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_EMAIL


async def sell_skip_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏭ ویدیو رد شد.\n\n"
        "مرحله ۵/۸ — لطفاً <b>ایمیل اکانت</b> را وارد کنید:",
        parse_mode="HTML",
    )
    return SELL_EMAIL


async def sell_receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["email"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ ایمیل ثبت شد.\n\n"
        "مرحله ۶/۸ — لطفاً <b>رمز عبور اکانت</b> را وارد کنید:",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_PASSWORD


async def sell_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["password"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ رمز ثبت شد.\n\n"
        "مرحله ۷/۸ — آیا می‌خواهید <b>ایمیل اکانت بعد از فروش تغییر کند؟</b>\n"
        "(برای امنیت خریدار پیشنهاد می‌شود)",
        reply_markup=sell_email_change_keyboard(),
        parse_mode="HTML",
    )
    return SELL_EMAIL_CHANGE_Q


async def sell_email_change_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ بسیار عالی!\n\n"
        "لطفاً <b>ایمیل جدیدی</b> که بعد از فروش روی اکانت ست می‌شود را وارد کنید:",
        parse_mode="HTML",
    )
    return SELL_NEW_EMAIL


async def sell_email_change_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["new_email"] = None
    await query.edit_message_text(
        "مرحله ۸/۸ — لطفاً <b>شماره تلفن</b> خود را وارد کنید:\n"
        "(برای ارتباط با خریدار پس از تأیید فروش)",
        parse_mode="HTML",
    )
    return SELL_PHONE


async def sell_receive_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_email"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ ایمیل جدید ثبت شد.\n\n"
        "مرحله ۸/۸ — لطفاً <b>شماره تلفن</b> خود را وارد کنید:\n"
        "(برای ارتباط با خریدار پس از تأیید فروش)",
        reply_markup=sell_cancel_keyboard(),
        parse_mode="HTML",
    )
    return SELL_PHONE


async def sell_receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    user = update.effective_user

    listing_id, unique_code = db.create_listing(
        seller_id=user.id,
        title=context.user_data["title"],
        description=context.user_data["description"],
        email=context.user_data["email"],
        password=context.user_data["password"],
        new_email=context.user_data.get("new_email"),
        phone=phone,
    )

    for file_id in context.user_data["photos"]:
        db.add_media(listing_id, "photo", file_id)
    if context.user_data.get("video"):
        db.add_media(listing_id, "video", context.user_data["video"])

    channel_text = (
        f"🎮 <b>{context.user_data['title']}</b>\n\n"
        f"📝 {context.user_data['description']}\n\n"
        f"🔑 کد یکتای آگهی: <code>{unique_code}</code>\n\n"
        "برای خرید این اکانت، کد بالا را در ربات وارد کنید."
    )

    photos = context.user_data["photos"]
    sent_msg = None
    channel_publish_ok = False

    try:
        if len(photos) == 1:
            sent_msg = await context.bot.send_photo(
                CHANNEL_ID, photo=photos[0],
                caption=channel_text, parse_mode="HTML",
            )
        elif len(photos) > 1:
            media_group = [InputMediaPhoto(photos[0], caption=channel_text, parse_mode="HTML")]
            media_group += [InputMediaPhoto(p) for p in photos[1:]]
            msgs = await context.bot.send_media_group(CHANNEL_ID, media_group)
            sent_msg = msgs[0]
        else:
            sent_msg = await context.bot.send_message(CHANNEL_ID, channel_text, parse_mode="HTML")
        channel_publish_ok = True
    except Exception:
        channel_publish_ok = False

    if sent_msg:
        db.set_channel_msg_id(listing_id, sent_msg.message_id)

    result_text = (
        f"✅ <b>آگهی شما با موفقیت ثبت و در کانال منتشر شد!</b>\n\n"
        f"🔑 کد یکتای آگهی: <code>{unique_code}</code>\n\n"
        "این کد برای شناسایی آگهی شما در فرآیند خرید استفاده می‌شود."
        if channel_publish_ok else
        f"✅ <b>آگهی شما ثبت شد.</b>\n\n"
        f"🔑 کد یکتای آگهی: <code>{unique_code}</code>\n\n"
        "⚠️ انتشار در کانال با خطا روبرو شد. با ادمین تماس بگیرید."
    )

    await update.message.reply_text(
        result_text,
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
        await update.callback_query.edit_message_text("❌ فرآیند ثبت آگهی لغو شد.")
    else:
        await update.message.reply_text("❌ فرآیند ثبت آگهی لغو شد.")
    await context.bot.send_message(
        user.id, "منوی اصلی:",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    return ConversationHandler.END


def sell_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 ثبت آگهی فروش$"), sell_start)],
        states={
            SELL_TITLE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_title),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_DESCRIPTION:   [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_description),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_PHOTOS:        [MessageHandler(filters.PHOTO, sell_receive_photo),
                                  CallbackQueryHandler(sell_end_photos_callback, pattern="^end_photos$"),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_VIDEO:         [MessageHandler(filters.VIDEO, sell_receive_video),
                                  CallbackQueryHandler(sell_skip_video_callback, pattern="^skip_video$"),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_EMAIL:         [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_email),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_PASSWORD:      [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_password),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_EMAIL_CHANGE_Q:[CallbackQueryHandler(sell_email_change_yes, pattern="^email_yes$"),
                                  CallbackQueryHandler(sell_email_change_no, pattern="^email_no$"),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_NEW_EMAIL:     [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_new_email),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
            SELL_PHONE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_receive_phone),
                                  CallbackQueryHandler(sell_cancel, pattern="^cancel_sell$")],
        },
        fallbacks=[
            CommandHandler("cancel", sell_cancel),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), sell_cancel),
        ],
        allow_reentry=True,
    )


# ====================================================
# هندلرهای خرید اکانت
# ====================================================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_access(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "🛒 <b>خرید اکانت</b>\n\n"
        "لطفاً <b>کد یکتای آگهی</b> را وارد کنید:\n"
        "(کد ۶ کاراکتری که در کانال درج شده)",
        parse_mode="HTML",
    )
    return BUY_ENTER_CODE


async def buy_receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    listing = db.get_listing_by_code(code)
    user = update.effective_user

    if not listing:
        await update.message.reply_text(
            "❌ آگهی‌ای با این کد یافت نشد.\n"
            "کد را بررسی کنید یا /cancel برای لغو:"
        )
        return BUY_ENTER_CODE

    if listing["status"] != "active":
        await update.message.reply_text(
            "⚠️ این آگهی دیگر فعال نیست.\n"
            "برای لغو /cancel را بزنید."
        )
        return BUY_ENTER_CODE

    if listing["seller_id"] == user.id:
        await update.message.reply_text(
            "❌ نمی‌توانید آگهی خودتان را بخرید!\n"
            "برای لغو /cancel را بزنید."
        )
        return BUY_ENTER_CODE

    if db.get_transaction_by_listing_and_buyer(listing["id"], user.id):
        await update.message.reply_text(
            "⚠️ شما قبلاً برای این آگهی تراکنش فعال دارید.\n"
            "برای لغو /cancel را بزنید."
        )
        return BUY_ENTER_CODE

    if db.get_active_transaction_by_listing(listing["id"]):
        await update.message.reply_text(
            "⚠️ این آگهی در حال حاضر در فرآیند خرید توسط خریدار دیگری است.\n"
            "لطفاً بعداً دوباره تلاش کنید.\n"
            "برای لغو /cancel را بزنید."
        )
        return BUY_ENTER_CODE

    db.lock_listing(listing["id"])
    transaction_id = db.create_transaction(listing["id"], user.id)
    context.user_data["buy_listing_id"] = listing["id"]
    context.user_data["buy_listing_title"] = listing["title"]
    context.user_data["buy_transaction_id"] = transaction_id

    await update.message.reply_text(
        f"✅ آگهی پیدا شد: <b>{listing['title']}</b>\n\n"
        "💳 <b>اطلاعات پرداخت:</b>\n"
        f"شماره کارت: <code>{CARD_NUMBER}</code>\n"
        f"به نام: <b>{CARD_OWNER}</b>\n\n"
        "⚠️ <b>هشدار مهم:</b>\n"
        "ارسال رسید جعلی = عدم تحویل اکانت + مسدود شدن دائمی حساب شما\n\n"
        "پس از واریز وجه، تصویر رسید بانکی را ارسال کنید:",
        parse_mode="HTML",
    )
    return BUY_SEND_RECEIPT


async def buy_receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text(
            "⚠️ لطفاً تصویر رسید بانکی را ارسال کنید (نه فایل یا متن):"
        )
        return BUY_SEND_RECEIPT

    photo_file_id = update.message.photo[-1].file_id
    transaction_id = context.user_data.get("buy_transaction_id")
    listing_title = context.user_data.get("buy_listing_title", "نامشخص")
    user = update.effective_user

    if not transaction_id:
        await update.message.reply_text("❌ خطا رخ داد. لطفاً دوباره /start بزنید.")
        return ConversationHandler.END

    db.set_receipt(transaction_id, photo_file_id)

    admin_text = (
        f"🧾 <b>رسید پرداخت جدید</b>\n\n"
        f"🛒 آگهی: <b>{listing_title}</b>\n"
        f"👤 خریدار: {user.full_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n🆔 آیدی: <code>{user.id}</code>\n"
        f"🔢 شناسه تراکنش: <code>{transaction_id}</code>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id, photo=photo_file_id,
                caption=admin_text, parse_mode="HTML",
                reply_markup=admin_receipt_keyboard(transaction_id),
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ رسید شما دریافت شد و برای بررسی ادمین ارسال شد.\n"
        "پس از تأیید، اطلاع‌رسانی خواهید شد.\n\n"
        "⏳ لطفاً صبور باشید.",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def buy_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()
    await update.message.reply_text(
        "❌ فرآیند خرید لغو شد.",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
    )
    return ConversationHandler.END


def buy_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 خرید اکانت$"), buy_start)],
        states={
            BUY_ENTER_CODE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_receive_code)],
            BUY_SEND_RECEIPT:[MessageHandler(filters.PHOTO, buy_receive_receipt),
                              MessageHandler(filters.TEXT & ~filters.COMMAND, buy_receive_receipt)],
        },
        fallbacks=[
            CommandHandler("cancel", buy_cancel),
            MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), buy_cancel),
        ],
        allow_reentry=True,
    )


# ====================================================
# Callback های تأیید/رد ادمین و فروشنده
# ====================================================

async def admin_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admin = update.effective_user

    if admin.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return

    transaction_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(transaction_id)
    if not tx:
        await query.edit_message_caption("❌ تراکنش یافت نشد.")
        return
    if tx["status"] != "pending_admin":
        await query.answer("این تراکنش قبلاً بررسی شده است.", show_alert=True)
        return

    db.admin_approve_transaction(transaction_id)
    listing = db.get_listing_by_id(tx["listing_id"])

    try:
        await context.bot.send_message(
            listing["seller_id"],
            f"✅ <b>پرداخت تأیید شد!</b>\n\n"
            f"🛒 آگهی: <b>{listing['title']}</b>\n\n"
            "خریدار وجه را واریز کرده و ادمین تأیید کرده است.\n"
            f"شما <b>{SELLER_CONFIRM_TIMEOUT_HOURS} ساعت</b> فرصت دارید تحویل اکانت را تأیید کنید.\n\n"
            "پس از تحویل روی دکمه زیر بزنید:",
            reply_markup=seller_confirm_keyboard(transaction_id),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n✅ تأیید شد توسط {admin.full_name}",
        parse_mode="HTML",
    )


async def admin_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admin = update.effective_user

    if admin.id not in ADMIN_IDS:
        await query.answer("⛔ شما ادمین نیستید!", show_alert=True)
        return

    transaction_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(transaction_id)
    if not tx:
        await query.edit_message_caption("❌ تراکنش یافت نشد.")
        return
    if tx["status"] != "pending_admin":
        await query.answer("این تراکنش قبلاً بررسی شده است.", show_alert=True)
        return

    db.admin_reject_transaction(transaction_id)
    listing = db.get_listing_by_id(tx["listing_id"])
    if listing and listing["status"] == "reserved":
        db.unlock_listing(tx["listing_id"])

    try:
        await context.bot.send_message(
            tx["buyer_id"],
            "❌ <b>رسید شما تأیید نشد.</b>\n\n"
            "رسید ارسالی معتبر نبود یا مشکلی وجود داشت.\n"
            "در صورت نیاز با ادمین تماس بگیرید.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n❌ رد شد توسط {admin.full_name}",
        parse_mode="HTML",
    )


async def seller_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    transaction_id = int(query.data.split("_")[-1])
    tx = db.get_transaction(transaction_id)
    if not tx:
        await query.edit_message_text("❌ تراکنش یافت نشد.")
        return

    listing = db.get_listing_by_id(tx["listing_id"])
    if not listing or listing["seller_id"] != user.id:
        await query.answer("⛔ این تراکنش متعلق به شما نیست!", show_alert=True)
        return
    if tx["status"] != "pending_seller":
        await query.answer("این تراکنش قبلاً پردازش شده است.", show_alert=True)
        return

    db.seller_confirm_transaction(transaction_id)
    db.deactivate_listing(listing["id"])

    buyer_text = (
        f"🎉 <b>خرید شما تأیید شد!</b>\n\n"
        f"🎮 <b>{listing['title']}</b>\n\n"
        f"📧 ایمیل: <code>{listing['email']}</code>\n"
        f"🔑 رمز عبور: <code>{listing['password']}</code>\n"
    )
    if listing["new_email"]:
        buyer_text += f"📨 ایمیل جدید (بعد از تحویل): <code>{listing['new_email']}</code>\n"
    seller_id = listing["seller_id"]
    buyer_text += f"\n📞 تماس مستقیم با فروشنده:\n<a href='tg://user?id={seller_id}'>کلیک کنید</a>"

    try:
        await context.bot.send_message(tx["buyer_id"], buyer_text, parse_mode="HTML")
    except Exception:
        pass

    buyer_id = tx["buyer_id"]
    await query.edit_message_text(
        "✅ <b>تحویل اکانت تأیید شد!</b>\n\n"
        "تراکنش با موفقیت کامل شد.\n"
        f"📞 تماس مستقیم با خریدار:\n<a href='tg://user?id={buyer_id}'>کلیک کنید</a>",
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
            "📋 شما هیچ آگهی‌ای ندارید.\n"
            "برای ثبت آگهی جدید از منوی «ثبت آگهی فروش» استفاده کنید.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user.id)),
        )
        return
    await update.message.reply_text(
        f"📋 <b>آگهی‌های شما ({len(listings)} آگهی):</b>\n"
        "برای مشاهده جزئیات روی هر آگهی کلیک کنید:",
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
    await query.edit_message_text(
        f"📋 <b>جزئیات آگهی</b>\n\n"
        f"📌 عنوان: {listing['title']}\n"
        f"📝 توضیحات: {listing['description']}\n"
        f"🔑 کد یکتا: <code>{listing['unique_code']}</code>\n"
        f"📊 وضعیت: {status}\n"
        f"📅 تاریخ ثبت: {listing['created_at'][:10]}\n",
        reply_markup=listing_actions_keyboard(listing_id, listing["status"]),
        parse_mode="HTML",
    )


async def delete_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[-1])
    listing = db.get_listing_by_id(listing_id)
    user = update.effective_user

    if not listing or listing["seller_id"] != user.id:
        await query.edit_message_text("❌ آگهی یافت نشد.")
        return
    if listing["status"] not in ("active", "reserved"):
        await query.answer("این آگهی قبلاً غیرفعال شده است.", show_alert=True)
        return

    db.deactivate_listing(listing_id)
    if listing["channel_msg_id"]:
        try:
            await context.bot.delete_message(CHANNEL_ID, listing["channel_msg_id"])
        except Exception:
            pass
    await query.edit_message_text(
        f"✅ آگهی «{listing['title']}» با موفقیت حذف و از کانال برداشته شد."
    )


async def my_listings_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    listings = db.get_seller_listings(user.id)
    if not listings:
        await query.edit_message_text("📋 شما هیچ آگهی‌ای ندارید.")
        return
    await query.edit_message_text(
        f"📋 <b>آگهی‌های شما ({len(listings)} آگهی):</b>\n"
        "برای مشاهده جزئیات روی هر آگهی کلیک کنید:",
        reply_markup=my_listings_keyboard(listings),
        parse_mode="HTML",
    )


# ====================================================
# هندلرهای پنل ادمین
# ====================================================

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "⚙️ <b>پنل مدیریت</b>\n\nگزینه مورد نظر را انتخاب کنید:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


async def list_banned_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    banned = db.get_banned_users()
    if not banned:
        await update.message.reply_text("✅ هیچ کاربری مسدود نیست.", reply_markup=admin_panel_keyboard())
        return
    text = "🚫 <b>کاربران مسدود:</b>\n\n"
    for u in banned:
        text += (
            f"👤 {u['full_name']}"
            + (f" (@{u['username']})" if u["username"] else "")
            + f"\n🆔 آیدی: <code>{u['user_id']}</code>"
            + (f"\n📌 دلیل: {u['ban_reason']}" if u["ban_reason"] else "")
            + "\n\n"
        )
    await update.message.reply_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")


async def unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "✅ <b>رفع مسدودیت</b>\n\nآیدی عددی کاربر مورد نظر را وارد کنید:",
        parse_mode="HTML",
    )
    return ADMIN_WAIT_UNBAN_ID


async def unban_receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ آیدی باید عدد باشد. دوباره وارد کنید:", reply_markup=admin_panel_keyboard())
        return ADMIN_WAIT_UNBAN_ID

    target_id = int(text)
    target = db.get_user(target_id)
    if not target:
        await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.", reply_markup=admin_panel_keyboard())
        return ConversationHandler.END
    if not target["is_banned"]:
        await update.message.reply_text("⚠️ این کاربر از قبل مسدود نیست.", reply_markup=admin_panel_keyboard())
        return ConversationHandler.END

    db.unban_user(target_id)
    try:
        await context.bot.send_message(
            target_id,
            "✅ مسدودیت حساب شما برداشته شد.\nاکنون می‌توانید از ربات استفاده کنید.",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ مسدودیت کاربر <code>{target_id}</code> با موفقیت رفع شد.",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await send_main_menu(update, context)
    return ConversationHandler.END


def admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✅ رفع مسدودیت کاربر$"), unban_start)],
        states={
            ADMIN_WAIT_UNBAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, unban_receive_id)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"), back_to_main)],
        allow_reentry=True,
    )


# ====================================================
# وظیفه دوره‌ای: بررسی Timeout ۷۲ ساعته
# ====================================================

async def check_seller_timeouts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """بررسی تراکنش‌هایی که فروشنده در مهلت مقرر تأیید نکرده."""
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

        db.ban_user(
            listing["seller_id"],
            reason=f"عدم تأیید تحویل اکانت در مهلت {SELLER_CONFIRM_TIMEOUT_HOURS} ساعته (تراکنش {tx['id']})",
        )
        db.deactivate_listing(listing["id"])
        db.unlock_listing(listing["id"])
        db.timeout_transaction(tx["id"])

        try:
            await context.bot.send_message(
                tx["buyer_id"],
                f"⚠️ <b>هشدار</b>\n\n"
                f"فروشنده آگهی «{listing['title']}» در مهلت {SELLER_CONFIRM_TIMEOUT_HOURS} ساعته "
                "تحویل اکانت را تأیید نکرد.\n\n"
                "فروشنده مسدود شد. برای پیگیری با ادمین تماس بگیرید.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🚨 <b>Timeout فروشنده</b>\n\n"
                    f"آگهی: {listing['title']}\n"
                    f"فروشنده: <code>{listing['seller_id']}</code>\n"
                    f"خریدار: <code>{tx['buyer_id']}</code>\n"
                    f"تراکنش: <code>{tx['id']}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        logger.info("Seller %s timed out — tx %s banned and deactivated.", listing["seller_id"], tx["id"])


# ====================================================
# راه‌اندازی اصلی
# ====================================================

def main() -> None:
    # سازگاری با Python 3.12+ — اطمینان از وجود event loop پیش از شروع PTB
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    db.init_db()
    logger.info("دیتابیس راه‌اندازی شد.")

    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # هندلرهای /start و عضویت
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"))
    app.add_handler(CallbackQueryHandler(accept_warning_callback,   pattern="^accept_warning$"))

    # مکالمه‌ها
    app.add_handler(sell_conversation())
    app.add_handler(buy_conversation())
    app.add_handler(admin_conversation())

    # هندلرهای منو
    app.add_handler(MessageHandler(filters.Regex("^⚙️ پنل مدیریت$"),         admin_panel_handler))
    app.add_handler(MessageHandler(filters.Regex("^🚫 لیست کاربران مسدود$"), list_banned_handler))
    app.add_handler(MessageHandler(filters.Regex("^🔙 بازگشت به منوی اصلی$"),back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^📋 آگهی‌های من$"),         my_listings_handler))

    # Callback های تأیید/رد
    app.add_handler(CallbackQueryHandler(admin_approve_callback,  pattern=r"^admin_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_reject_callback,   pattern=r"^admin_reject_\d+$"))
    app.add_handler(CallbackQueryHandler(seller_confirm_callback, pattern=r"^seller_confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(view_listing_callback,   pattern=r"^view_listing_\d+$"))
    app.add_handler(CallbackQueryHandler(delete_listing_callback, pattern=r"^delete_listing_\d+$"))
    app.add_handler(CallbackQueryHandler(my_listings_back_callback, pattern="^my_listings_back$"))

    # وظیفه دوره‌ای timeout
    app.job_queue.run_repeating(
        check_seller_timeouts,
        interval=TIMEOUT_CHECK_INTERVAL_MINUTES * 60,
        first=60,
    )

    logger.info("ربات شروع به کار کرد (Polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
