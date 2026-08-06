# -*- coding: utf-8 -*-
import sqlite3
import random
import string
from datetime import datetime
from config import DATABASE_PATH, BUYER_COMMISSION_PCT, SELLER_COMMISSION_PCT


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ===========================
# محاسبه کارمزد
# ===========================

def calculate_commission(base_price_toman: int) -> tuple[int, int, int]:
    """
    محاسبه کارمزد واسط‌گری.
    برمی‌گرداند: (مبلغ پرداختی خریدار، سهم فروشنده، سود ربات)
    همه مقادیر به تومان (عدد صحیح).
    """
    buyer_pays    = round(base_price_toman * (1 + BUYER_COMMISSION_PCT / 100))
    seller_gets   = round(base_price_toman * (1 - SELLER_COMMISSION_PCT / 100))
    bot_profit    = buyer_pays - seller_gets
    return buyer_pays, seller_gets, bot_profit


def fmt_price(toman: int) -> str:
    """نمایش فارسی قیمت."""
    return f"{toman:,} تومان"


# ===========================
# راه‌اندازی دیتابیس
# ===========================

def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                full_name      TEXT,
                joined_at      TEXT NOT NULL DEFAULT (datetime('now')),
                warned         INTEGER NOT NULL DEFAULT 0,
                is_banned      INTEGER NOT NULL DEFAULT 0,
                ban_reason     TEXT,
                referred_by    INTEGER,
                referral_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS wallets (
                user_id  INTEGER PRIMARY KEY,
                balance  INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                type        TEXT NOT NULL,
                amount      INTEGER NOT NULL,
                ref_id      INTEGER,
                note        TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS wallet_charges (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                amount           INTEGER NOT NULL,
                receipt_file_id  TEXT,
                status           TEXT NOT NULL DEFAULT 'pending',
                created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS listings (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_code        TEXT UNIQUE NOT NULL,
                seller_id          INTEGER NOT NULL,
                category           TEXT NOT NULL DEFAULT 'coc_account',
                title              TEXT NOT NULL,
                description        TEXT NOT NULL,
                price              TEXT NOT NULL DEFAULT '',
                price_toman        INTEGER,
                email              TEXT NOT NULL DEFAULT '',
                password           TEXT NOT NULL DEFAULT '',
                new_email          TEXT,
                phone              TEXT NOT NULL DEFAULT '',
                clan_name          TEXT,
                clan_level         TEXT,
                member_count       TEXT,
                clan_trophies      TEXT,
                seller_card_number TEXT,
                channel_msg_id     INTEGER,
                status             TEXT NOT NULL DEFAULT 'draft',
                created_at         TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (seller_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS listing_media (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id  INTEGER NOT NULL,
                media_type  TEXT NOT NULL,
                file_id     TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id          INTEGER NOT NULL,
                buyer_id            INTEGER NOT NULL,
                receipt_file_id     TEXT,
                payment_method      TEXT NOT NULL DEFAULT 'card',
                buyer_amount        INTEGER,
                seller_amount       INTEGER,
                admin_approved_at   TEXT,
                seller_confirmed_at TEXT,
                buyer_confirmed_at  TEXT,
                status              TEXT NOT NULL DEFAULT 'pending_receipt',
                created_at          TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (listing_id) REFERENCES listings(id),
                FOREIGN KEY (buyer_id)   REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_users_referred_by    ON users(referred_by);
            CREATE INDEX IF NOT EXISTS idx_listings_seller       ON listings(seller_id);
            CREATE INDEX IF NOT EXISTS idx_listings_status       ON listings(status);
            CREATE INDEX IF NOT EXISTS idx_listings_channel_msg  ON listings(channel_msg_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_listing  ON transactions(listing_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_buyer    ON transactions(buyer_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_status   ON transactions(status);
            CREATE INDEX IF NOT EXISTS idx_wallet_tx_user        ON wallet_transactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_wallet_charges_user   ON wallet_charges(user_id);
            CREATE INDEX IF NOT EXISTS idx_wallet_charges_status ON wallet_charges(status);
        """)

    # مهاجرت روی دیتابیس‌های قدیمی
    _run_migrations()


def _run_migrations() -> None:
    migrations = [
        # users
        "ALTER TABLE users ADD COLUMN referred_by    INTEGER",
        "ALTER TABLE users ADD COLUMN referral_count INTEGER NOT NULL DEFAULT 0",
        # listings
        "ALTER TABLE listings ADD COLUMN price_toman   INTEGER",
        "ALTER TABLE listings ADD COLUMN category      TEXT NOT NULL DEFAULT 'coc_account'",
        "ALTER TABLE listings ADD COLUMN clan_name     TEXT",
        "ALTER TABLE listings ADD COLUMN clan_level    TEXT",
        "ALTER TABLE listings ADD COLUMN member_count  TEXT",
        "ALTER TABLE listings ADD COLUMN clan_trophies TEXT",
        # شماره کارت فروشنده
        "ALTER TABLE listings ADD COLUMN seller_card_number TEXT",
        # transactions
        "ALTER TABLE transactions ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'card'",
        "ALTER TABLE transactions ADD COLUMN buyer_amount   INTEGER",
        "ALTER TABLE transactions ADD COLUMN seller_amount  INTEGER",
        "ALTER TABLE transactions ADD COLUMN buyer_confirmed_at TEXT",
        # price TEXT (backward compat)
        "ALTER TABLE listings ADD COLUMN price TEXT NOT NULL DEFAULT ''",
        # email/phone optional for old rows
        "ALTER TABLE listings ADD COLUMN email    TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE listings ADD COLUMN password TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE listings ADD COLUMN phone    TEXT NOT NULL DEFAULT ''",
    ]
    with get_connection() as conn:
        for sql in migrations:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass


# ===========================
# مدیریت کاربران
# ===========================

def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name),
        )


def get_user(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def is_banned(user_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return bool(row and row["is_banned"])


def set_warned(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET warned = 1 WHERE user_id = ?", (user_id,))


def ban_user(user_id: int, reason: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
            (reason, user_id),
        )


def unban_user(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?", (user_id,))


def get_banned_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users WHERE is_banned = 1").fetchall()


# ===========================
# سیستم رفرال
# ===========================

def set_referrer(user_id: int, referrer_id: int) -> bool:
    """
    ثبت دعوت‌کننده. فقط یک‌بار، فقط اگه قبلاً ست نشده.
    برمی‌گرداند True اگه موفق بود.
    """
    with get_connection() as conn:
        row = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row and row["referred_by"] is not None:
            return False
        if row is None:
            return False
        conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
        # افزایش شمارنده دعوت‌کننده
        conn.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?",
            (referrer_id,),
        )
        return True


def get_referral_count(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["referral_count"] if row else 0


# ===========================
# کیف پول
# ===========================

def ensure_wallet(user_id: int) -> None:
    """اگه کیف پول وجود نداشت، می‌سازد."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)",
            (user_id,),
        )


def get_wallet_balance(user_id: int) -> int:
    ensure_wallet(user_id)
    with get_connection() as conn:
        row = conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        return row["balance"] if row else 0


def credit_wallet(user_id: int, amount: int, tx_type: str, ref_id: int | None = None, note: str = "") -> None:
    """واریز به کیف پول (اتمیک)."""
    ensure_wallet(user_id)
    with get_connection() as conn:
        conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, type, amount, ref_id, note) VALUES (?, ?, ?, ?, ?)",
            (user_id, tx_type, amount, ref_id, note),
        )


def debit_wallet_atomic(user_id: int, amount: int, tx_type: str, ref_id: int | None = None, note: str = "") -> bool:
    """
    کسر از کیف پول (اتمیک با چک موجودی).
    برمی‌گرداند True اگه موفق بود، False اگه موجودی کافی نبود.
    """
    ensure_wallet(user_id)
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, user_id, amount),
        )
        if cur.rowcount == 0:
            return False
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, type, amount, ref_id, note) VALUES (?, ?, ?, ?, ?)",
            (user_id, tx_type, -amount, ref_id, note),
        )
        return True


def create_wallet_charge(user_id: int, amount: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO wallet_charges (user_id, amount) VALUES (?, ?)",
            (user_id, amount),
        )
        return cur.lastrowid


def set_wallet_charge_receipt(charge_id: int, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE wallet_charges SET receipt_file_id = ? WHERE id = ?",
            (file_id, charge_id),
        )


def approve_wallet_charge(charge_id: int) -> tuple[int, int] | None:
    """تأیید شارژ کیف پول. برمی‌گرداند (user_id, amount) یا None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, amount, status FROM wallet_charges WHERE id = ?",
            (charge_id,),
        ).fetchone()
        if not row or row["status"] != "pending":
            return None
        conn.execute("UPDATE wallet_charges SET status = 'approved' WHERE id = ?", (charge_id,))
    credit_wallet(row["user_id"], row["amount"], "charge", charge_id, "شارژ کیف پول")
    return row["user_id"], row["amount"]


def reject_wallet_charge(charge_id: int) -> int | None:
    """رد شارژ. برمی‌گرداند user_id یا None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, status FROM wallet_charges WHERE id = ?", (charge_id,)
        ).fetchone()
        if not row or row["status"] != "pending":
            return None
        conn.execute("UPDATE wallet_charges SET status = 'rejected' WHERE id = ?", (charge_id,))
        return row["user_id"]


def get_pending_wallet_charges() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM wallet_charges WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()


def get_wallet_transactions(user_id: int, limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


# ===========================
# مدیریت آگهی‌ها
# ===========================

def generate_unique_code() -> str:
    chars = string.ascii_uppercase + string.digits
    with get_connection() as conn:
        while True:
            code = "".join(random.choices(chars, k=6))
            if not conn.execute("SELECT 1 FROM listings WHERE unique_code = ?", (code,)).fetchone():
                return code


def create_listing(
    seller_id: int,
    category: str,
    title: str,
    description: str,
    price: str,
    price_toman: int | None,
    email: str = "",
    password: str = "",
    new_email: str | None = None,
    phone: str = "",
    clan_name: str | None = None,
    clan_level: str | None = None,
    member_count: str | None = None,
    clan_trophies: str | None = None,
    seller_card_number: str = "",
) -> tuple[int, str]:
    code = generate_unique_code()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO listings
                (unique_code, seller_id, category, title, description,
                 price, price_toman, email, password, new_email, phone,
                 clan_name, clan_level, member_count, clan_trophies,
                 seller_card_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
            """,
            (code, seller_id, category, title, description,
             price, price_toman, email, password, new_email, phone,
             clan_name, clan_level, member_count, clan_trophies,
             seller_card_number),
        )
        return cur.lastrowid, code


def add_media(listing_id: int, media_type: str, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO listing_media (listing_id, media_type, file_id) VALUES (?, ?, ?)",
            (listing_id, media_type, file_id),
        )


def get_listing_media(listing_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listing_media WHERE listing_id = ?", (listing_id,)
        ).fetchall()


def set_channel_msg_id(listing_id: int, msg_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE listings SET channel_msg_id = ? WHERE id = ?", (msg_id, listing_id))


def approve_listing(listing_id: int) -> None:
    """ادمین آگهی را تأیید کرد → وضعیت به active."""
    with get_connection() as conn:
        conn.execute("UPDATE listings SET status = 'active' WHERE id = ?", (listing_id,))


def reject_listing(listing_id: int) -> None:
    """ادمین آگهی را رد کرد."""
    with get_connection() as conn:
        conn.execute("UPDATE listings SET status = 'rejected' WHERE id = ?", (listing_id,))


def lock_listing(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE listings SET status = 'reserved' WHERE id = ? AND status = 'active'",
            (listing_id,),
        )


def unlock_listing(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE listings SET status = 'active' WHERE id = ? AND status = 'reserved'",
            (listing_id,),
        )


def deactivate_listing(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE listings SET status = 'inactive' WHERE id = ?", (listing_id,))


def mark_listing_sold(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE listings SET status = 'sold' WHERE id = ?", (listing_id,))


def get_listing_by_code(code: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM listings WHERE unique_code = ?", (code,)).fetchone()


def get_listing_by_id(listing_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()


def get_seller_listings(seller_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listings WHERE seller_id = ? ORDER BY created_at DESC",
            (seller_id,),
        ).fetchall()


def get_all_listings(status_filter: str | None = None) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if status_filter:
            return conn.execute(
                "SELECT * FROM listings WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        return conn.execute("SELECT * FROM listings ORDER BY created_at DESC").fetchall()


def get_active_transaction_by_listing(listing_id: int) -> "sqlite3.Row | None":
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM transactions
            WHERE listing_id = ?
              AND status NOT IN ('rejected', 'timeout', 'cancelled')
            ORDER BY created_at DESC LIMIT 1
            """,
            (listing_id,),
        ).fetchone()


# ===========================
# مدیریت تراکنش‌ها
# ===========================

def create_transaction(
    listing_id: int,
    buyer_id: int,
    payment_method: str = "card",
    buyer_amount: int | None = None,
    seller_amount: int | None = None,
) -> int:
    with get_connection() as conn:
        initial_status = "pending_receipt" if payment_method == "card" else "pending_seller"
        cur = conn.execute(
            """
            INSERT INTO transactions
                (listing_id, buyer_id, payment_method, buyer_amount, seller_amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (listing_id, buyer_id, payment_method, buyer_amount, seller_amount, initial_status),
        )
        return cur.lastrowid


def set_receipt(transaction_id: int, file_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE transactions SET receipt_file_id = ?, status = 'pending_admin' WHERE id = ?",
            (file_id, transaction_id),
        )


def admin_approve_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE transactions
            SET status = 'pending_seller', admin_approved_at = datetime('now')
            WHERE id = ?
            """,
            (transaction_id,),
        )


def admin_reject_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE transactions SET status = 'rejected' WHERE id = ?", (transaction_id,))


def seller_confirm_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE transactions
            SET status = 'pending_buyer', seller_confirmed_at = datetime('now')
            WHERE id = ?
            """,
            (transaction_id,),
        )


def buyer_confirm_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE transactions
            SET status = 'completed', buyer_confirmed_at = datetime('now')
            WHERE id = ?
            """,
            (transaction_id,),
        )


def get_transaction(transaction_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()


def get_pending_seller_transactions() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE status = 'pending_seller' AND admin_approved_at IS NOT NULL"
        ).fetchall()


def get_pending_buyer_transactions() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE status = 'pending_buyer' AND seller_confirmed_at IS NOT NULL"
        ).fetchall()


def timeout_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE transactions SET status = 'timeout' WHERE id = ?", (transaction_id,))


def get_transaction_by_listing_and_buyer(listing_id: int, buyer_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM transactions
            WHERE listing_id = ? AND buyer_id = ?
              AND status NOT IN ('rejected', 'timeout')
            ORDER BY created_at DESC LIMIT 1
            """,
            (listing_id, buyer_id),
        ).fetchone()


# ===========================
# گزارش‌های مالی ادمین
# ===========================

def get_financial_summary() -> dict:
    """خلاصه مالی برای پنل ادمین."""
    with get_connection() as conn:
        completed = conn.execute(
            "SELECT COUNT(*), SUM(buyer_amount), SUM(seller_amount) FROM transactions WHERE status = 'completed'"
        ).fetchone()
        pending_charges = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM wallet_charges WHERE status = 'pending'"
        ).fetchone()
        approved_charges = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM wallet_charges WHERE status = 'approved'"
        ).fetchone()
        return {
            "completed_count":   completed[0] or 0,
            "total_buyer_paid":  completed[1] or 0,
            "total_seller_got":  completed[2] or 0,
            "bot_profit":        (completed[1] or 0) - (completed[2] or 0),
            "pending_charges_count": pending_charges[0] or 0,
            "pending_charges_sum":   pending_charges[1] or 0,
            "approved_charges_count": approved_charges[0] or 0,
            "approved_charges_sum":   approved_charges[1] or 0,
        }


def get_recent_wallet_transactions(limit: int = 30) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM wallet_transactions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_all_wallet_charges(status_filter: str | None = None, limit: int = 30) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if status_filter:
            return conn.execute(
                "SELECT * FROM wallet_charges WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM wallet_charges ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
