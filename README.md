# ربات واسطه خرید و فروش اکانت بازی

ربات تلگرامی برای خرید و فروش اکانت‌های بازی با سیستم واسطه امن.

## ویژگی‌ها

- ثبت آگهی فروش با عنوان، توضیحات، **قیمت**، تصاویر، ویدیو، ایمیل و رمز
- انتشار خودکار آگهی در کانال با **لینک ربات**
- سیستم خرید با کد یکتا و رسید بانکی
- تأیید پرداخت توسط ادمین
- تأیید تحویل توسط فروشنده (با timeout ۷۲ ساعته)
- **پنل ادمین کامل**: مدیریت کاربران + مدیریت آگهی‌ها + جستجو
- **Health-check HTTP endpoint** برای UptimeRobot / Render

## متغیرهای محیطی

| متغیر | اجباری | توضیح |
|---|---|---|
| `BOT_TOKEN` | ✅ | توکن ربات از @BotFather |
| `CHANNEL_ID` | ✅ | آیدی کانال (`@channel` یا عددی) |
| `CHANNEL_LINK` | ✅ | لینک دعوت به کانال |
| `ADMIN_IDS` | ✅ | آیدی عددی ادمین‌ها، جداشده با ویرگول |
| `BOT_USERNAME` | ❌ | یوزرنیم ربات (بدون @) — برای لینک در کانال |
| `CARD_NUMBER` | ✅ | شماره کارت بانکی |
| `CARD_OWNER` | ✅ | نام صاحب کارت |
| `DATABASE_PATH` | ❌ | مسیر دیتابیس SQLite (پیش‌فرض: `bot_data.db`) |
| `TIMEOUT_CHECK_INTERVAL_MINUTES` | ❌ | فاصله بررسی timeout (پیش‌فرض: `30`) |
| `SELLER_CONFIRM_TIMEOUT_HOURS` | ❌ | مهلت فروشنده به ساعت (پیش‌فرض: `72`) |
| `PORT` | ❌ | پورت health-check — Render خودکار تنظیم می‌کند (پیش‌فرض: `8080`) |

## Health-check برای UptimeRobot

ربات یک سرور HTTP ساده روی `PORT` اجرا می‌کند. آدرس زیر را در UptimeRobot وارد کنید:

```
https://<your-render-url>/
```

پاسخ `200 OK` برمی‌گرداند.

## اجرا

```bash
pip install -r requirements.txt
cp .env.example .env
# مقادیر .env را پر کنید
python main.py
```

## دیپلوی روی Render

1. `Start Command` را روی `python main.py` قرار دهید.
2. متغیرهای محیطی را از `.env.example` وارد کنید.
3. Render مقدار `PORT` را خودکار تنظیم می‌کند.
4. آدرس سرویس Render را در UptimeRobot ثبت کنید (Health Check — HTTP — هر ۵ دقیقه).
