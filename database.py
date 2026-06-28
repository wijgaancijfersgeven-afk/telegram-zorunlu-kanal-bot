import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL UNIQUE,
                channel_name TEXT,
                invite_link TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TEXT DEFAULT (datetime('now')),
                is_member INTEGER DEFAULT 0,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                sent_count INTEGER DEFAULT 0
            );
        """)

        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("reward_link", "https://t.me/+aceUsVtKUB03OWI8")
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("welcome_message", "👋 Merhaba {name}!\n\nDevam etmek için aşağıdaki kanallara katılman gerekiyor.")
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("success_message", "✅ Tebrikler! Tüm kanallara katıldın.\n\nİşte özel linkin:")
        )
        conn.commit()


def get_setting(key: str) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()


def get_all_channels():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM channels ORDER BY id").fetchall()


def add_channel(channel_id: str, channel_name: str = "", invite_link: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO channels (channel_id, channel_name, invite_link) VALUES (?, ?, ?)",
            (channel_id, channel_name, invite_link)
        )
        conn.commit()


def remove_channel(channel_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
        conn.commit()


def upsert_user(user_id: int, username: str = "", first_name: str = ""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_seen=excluded.last_seen
        """, (user_id, username or "", first_name or "", datetime.now().isoformat()))
        conn.commit()


def set_user_member(user_id: int, is_member: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET is_member=? WHERE user_id=?",
            (1 if is_member else 0, user_id)
        )
        conn.commit()


def get_user_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
        return row["c"]


def get_member_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_member=1").fetchone()
        return row["c"]


def get_all_user_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]


def save_broadcast(message: str, sent_count: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO broadcasts (message, sent_count) VALUES (?, ?)",
            (message, sent_count)
        )
        conn.commit()


def get_broadcast_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM broadcasts").fetchone()
        return row["c"]
