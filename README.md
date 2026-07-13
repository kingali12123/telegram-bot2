# ربات واسطه خرید و فروش اکانت بازی 🎮

ربات تلگرام برای واسطه‌گری خرید و فروش اکانت بازی‌های **کلش آف کلنز، فری‌فایر، پابجی و کالاف‌دیوتی**.

## ✨ قابلیت‌ها

- 🔒 **قفل عضویت کانال** — کاربر تا عضو کانال نشود نمی‌تواند از ربات استفاده کند
- ⚠️ **هشدار ضد کلاهبرداری** — یک‌بار به کاربر نشان داده می‌شود و تأیید می‌گیرد
- 📢 **ثبت آگهی فروش** — فرآیند گام‌به‌گام با دریافت تصویر، ویدیو، ایمیل، رمز و شماره تلفن
- 🛒 **فرآیند خرید** — ورود کد یکتا، ارسال رسید، تأیید ادمین، تأیید فروشنده
- ⏱️ **تایمر ۷۲ ساعته** — اگر فروشنده تأیید نکند، مسدود و آگهی حذف می‌شود
- 📋 **مدیریت آگهی‌ها** — کاربر می‌تواند آگهی‌هایش را ببیند و حذف کند
- ⚙️ **پنل مدیریت** — فقط برای ادمین‌ها: مشاهده کاربران مسدود و رفع مسدودیت

---

## 📁 ساختار فایل‌ها

```
telegram_bot/
├── main.py                  # نقطه ورود — اجرای ربات
├── config.py                # خواندن تنظیمات از Environment Variables
├── database.py              # مدیریت دیتابیس SQLite
├── keyboards.py             # دکمه‌های شیشه‌ای و منوها
├── handlers/
│   ├── __init__.py
│   ├── common.py            # توابع کمکی مشترک (بررسی دسترسی، عضویت)
│   ├── start.py             # هندلر /start و هشدار
│   ├── sell.py              # فرآیند ثبت آگهی فروش
│   ├── buy.py               # فرآیند خرید و تأیید
│   ├── admin.py             # پنل مدیریت ادمین
│   └── my_listings.py       # مدیریت آگهی‌های کاربر
├── requirements.txt
├── .env.example             # نمونه متغیرهای محیطی
├── .gitignore
└── README.md
```

---

## ⚙️ متغیرهای محیطی موردنیاز

| متغیر | توضیح | مثال |
|---|---|---|
| `BOT_TOKEN` | توکن ربات از @BotFather | `1234567890:ABCDEF...` |
| `CHANNEL_ID` | آیدی کانال | `@mychannel` یا `-1001234567890` |
| `CHANNEL_LINK` | لینک دعوت کانال | `https://t.me/mychannel` |
| `ADMIN_IDS` | آیدی‌های عددی ادمین‌ها (با ویرگول) | `123456789,987654321` |
| `CARD_NUMBER` | شماره کارت بانکی | `6037-XXXX-XXXX-XXXX` |
| `CARD_OWNER` | نام صاحب کارت | `علی محمدی` |
| `DATABASE_PATH` | مسیر فایل دیتابیس (اختیاری) | `bot_data.db` |
| `TIMEOUT_CHECK_INTERVAL_MINUTES` | فاصله بررسی timeout (اختیاری) | `30` |
| `SELLER_CONFIRM_TIMEOUT_HOURS` | مهلت تأیید فروشنده (اختیاری) | `72` |

---

## 🚀 راهنمای نصب و اجرا

### الف) تنظیم Secrets در Replit

1. پروژه را در Replit باز کنید.
2. از نوار کناری چپ روی آیکون 🔒 **Secrets** کلیک کنید.
3. به ازای هر متغیر بالا یک Secret جدید اضافه کنید:
   - **Key**: نام متغیر (مثلاً `BOT_TOKEN`)
   - **Value**: مقدار واقعی
4. ربات را با دستور زیر اجرا کنید:

```bash
cd telegram_bot
pip install -r requirements.txt
python main.py
```

> ⚠️ در Replit هیچ‌وقت مقادیر حساس را مستقیم در کد ننویسید — همیشه از Secrets استفاده کنید.

---

### ب) دانلود پروژه از Replit

1. در Replit از منوی سه‌نقطه (⋮) بالا سمت راست گزینه **Download as zip** را انتخاب کنید.
2. فایل zip را روی کامپیوترتان extract کنید.
3. پوشه `telegram_bot/` را جدا نگه دارید — این پوشه‌ای است که باید آپلود کنید.

---

### ج) آپلود در GitHub

1. یک ریپازیتوری جدید خصوصی یا عمومی در [github.com](https://github.com) بسازید.
2. ترمینال را باز کنید و دستورات زیر را اجرا کنید:

```bash
cd telegram_bot
git init
git add .
git commit -m "Initial commit — Telegram bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

> ⚠️ مطمئن شوید فایل `.env` در `.gitignore` باشد تا اطلاعات حساس آپلود نشود.

---

### د) دیپلوی روی Render

#### ۱. ساخت سرویس جدید

1. به [render.com](https://render.com) بروید و وارد شوید.
2. روی **New +** کلیک کنید و **Background Worker** را انتخاب کنید.
   - (ربات polling نیاز به Web Service ندارد — Background Worker کافی است)
3. ریپازیتوری GitHub خود را متصل کنید.

#### ۲. تنظیمات سرویس

| فیلد | مقدار |
|---|---|
| **Name** | نام دلخواه (مثلاً `game-account-bot`) |
| **Root Directory** | `telegram_bot` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |

#### ۳. تنظیم Environment Variables در Render

1. در تب **Environment** سرویس، روی **Add Environment Variable** کلیک کنید.
2. تمام متغیرهای جدول بالا را اضافه کنید.

> ⚠️ مقدار `DATABASE_PATH` را به `bot_data.db` تنظیم کنید.  
> ⚠️ در Render فایل دیتابیس پایدار نیست (با هر deploy پاک می‌شود). برای محیط Production از یک دیتابیس خارجی مثل **Turso** یا **PlanetScale** استفاده کنید، یا **Render Disk** اضافه کنید.

#### ۴. دیپلوی

روی **Create Background Worker** کلیک کنید. Render به‌طور خودکار:
- کدها را از GitHub pull می‌کند
- `pip install -r requirements.txt` را اجرا می‌کند
- ربات را با `python main.py` راه‌اندازی می‌کند

---

## 📌 نکات مهم

- **دیتابیس**: SQLite برای محیط توسعه مناسب است. در Render حتماً Persistent Disk یا دیتابیس خارجی استفاده کنید.
- **Job Queue**: برای مکانیزم ۷۲ ساعته از `python-telegram-bot[job-queue]` (با APScheduler) استفاده شده که پس از ری‌استارت سرور از timestamp دیتابیس بازیابی می‌شود.
- **ادمین**: آیدی عددی تلگرام خود را از @userinfobot بگیرید.
- **کانال**: ربات را حتماً به کانال به‌عنوان Admin اضافه کنید تا بتواند عضویت کاربران را چک کند.
