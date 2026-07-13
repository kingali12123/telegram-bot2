# -*- coding: utf-8 -*-
import sqlite3
import random
import string
from datetime import datetime
from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """ایجاد جداول در صورت نبودن."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                joined_at   TEXT NOT NULL DEFAULT (datetime('now')),
                warned      INTEGER NOT NULL DEFAULT 0,
                is_banned   INTEGER NOT NULL DEFAULT 0,
                ban_reason  TEXT
            );

            CREATE TABLE IF NOT EXISTS listings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_code     TEXT UNIQUE NOT NULL,
                seller_id       INTEGER NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL,
                email           TEXT NOT NULL,
                password        TEXT NOT NULL,
                new_email       TEXT,
                phone           TEXT NOT NULL,
                channel_msg_id  INTEGER,
                status          TEXT NOT NULL DEFAULT 'active',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
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
                admin_approved_at   TEXT,
                seller_confirmed_at TEXT,
                status              TEXT NOT NULL DEFAULT 'pending_receipt',
                created_at          TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (listing_id) REFERENCES listings(id),
                FOREIGN KEY (buyer_id) REFERENCES users(user_id)
            );
        """)


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
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def is_banned(user_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT is_banned FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return bool(row and row["is_banned"])


def set_warned(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET warned = 1 WHERE user_id = ?", (user_id,)
        )


def ban_user(user_id: int, reason: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
            (reason, user_id),
        )


def unban_user(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?",
            (user_id,),
        )


def get_banned_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE is_banned = 1"
        ).fetchall()


# ===========================
# مدیریت آگهی‌ها
# ===========================

def generate_unique_code() -> str:
    """تولید کد یکتای ۶ کاراکتری بزرگ و عدد."""
    chars = string.ascii_uppercase + string.digits
    with get_connection() as conn:
        while True:
            code = "".join(random.choices(chars, k=6))
            exists = conn.execute(
                "SELECT 1 FROM listings WHERE unique_code = ?", (code,)
            ).fetchone()
            if not exists:
                return code


def create_listing(
    seller_id: int,
    title: str,
    description: str,
    email: str,
    password: str,
    new_email: str | None,
    phone: str,
) -> tuple[int, str]:
    """ایجاد آگهی جدید. برمی‌گرداند (id, unique_code)."""
    code = generate_unique_code()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO listings
                (unique_code, seller_id, title, description, email, password, new_email, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, seller_id, title, description, email, password, new_email, phone),
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
        conn.execute(
            "UPDATE listings SET channel_msg_id = ? WHERE id = ?",
            (msg_id, listing_id),
        )


def lock_listing(listing_id: int) -> None:
    """وضعیت آگهی را به 'reserved' تغییر می‌دهد تا خریدار دیگری نتواند وارد شود."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE listings SET status = 'reserved' WHERE id = ? AND status = 'active'",
            (listing_id,),
        )


def unlock_listing(listing_id: int) -> None:
    """آگهی رزرو‌شده را دوباره به حالت فعال برمی‌گرداند (وقتی رد یا timeout شود)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE listings SET status = 'active' WHERE id = ? AND status = 'reserved'",
            (listing_id,),
        )


def get_active_transaction_by_listing(listing_id: int) -> "sqlite3.Row | None":
    """بررسی می‌کند آیا تراکنش فعالی برای این آگهی وجود دارد."""
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


def get_listing_by_code(code: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listings WHERE unique_code = ?", (code,)
        ).fetchone()


def get_listing_by_id(listing_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()


def get_seller_listings(seller_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM listings WHERE seller_id = ? ORDER BY created_at DESC",
            (seller_id,),
        ).fetchall()


def deactivate_listing(listing_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE listings SET status = 'inactive' WHERE id = ?", (listing_id,)
        )


# ===========================
# مدیریت تراکنش‌ها
# ===========================

def create_transaction(listing_id: int, buyer_id: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions (listing_id, buyer_id, status)
            VALUES (?, ?, 'pending_receipt')
            """,
            (listing_id, buyer_id),
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
        conn.execute(
            "UPDATE transactions SET status = 'rejected' WHERE id = ?",
            (transaction_id,),
        )


def seller_confirm_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE transactions
            SET status = 'completed', seller_confirmed_at = datetime('now')
            WHERE id = ?
            """,
            (transaction_id,),
        )


def get_transaction(transaction_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()


def get_pending_seller_transactions() -> list[sqlite3.Row]:
    """تراکنش‌هایی که ادمین تأیید کرده ولی فروشنده هنوز تأیید نکرده."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM transactions WHERE status = 'pending_seller' AND admin_approved_at IS NOT NULL"
        ).fetchall()


def timeout_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE transactions SET status = 'timeout' WHERE id = ?",
            (transaction_id,),
        )


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
