import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
                last_name TEXT,
                joined_at TEXT DEFAULT (datetime('now')),
                is_member INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                last_seen TEXT,
                total_starts INTEGER DEFAULT 1,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                reward_given INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                channels_joined INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                confirmed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                target TEXT DEFAULT 'all',
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                sent_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reward_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,
                url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Mevcut tabloya sütun ekle (eski DB için)
        for col, definition in [
            ("referral_count", "INTEGER DEFAULT 0"),
            ("referred_by", "INTEGER DEFAULT NULL"),
            ("reward_given", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except Exception:
                pass

        defaults = {
            "welcome_message": "👋 Merhaba <b>{name}</b>!\n\nDevam etmek için aşağıdaki kanallara katılman gerekiyor. 👇",
            "success_message": "✅ <b>Tebrikler!</b> Tüm kanallara katıldın.\n\nŞimdi <b>5 kişiyi</b> davet etmen gerekiyor.\nDavet ettiklerin de kanallara katılmalı.",
            "pending_message": "⏳ Henüz tüm kanallara katılmadın!\n\nLütfen tüm kanalları takip edip tekrar dene.",
            "reward_message": "🎉 <b>Tebrikler! 5 davetini tamamladın!</b>\n\nİşte sana özel link:",
            "maintenance_mode": "0",
            "maintenance_message": "🔧 Bot şu an bakımda. Lütfen daha sonra tekrar deneyin.",
            "force_join": "1",
            "bot_active": "1",
            "join_button_text": "✅ Katıldım, Kontrol Et",
            "required_refs": "5",
        }
        for key, val in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

        conn.execute("INSERT OR IGNORE INTO reward_links (label, url) VALUES (?, ?)",
                     ("Ana Grup", "https://t.me/+aceUsVtKUB03OWI8"))
        conn.commit()


# ─── Settings ────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()


# ─── Channels ────────────────────────────────────────────────

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


# ─── Users ───────────────────────────────────────────────────

def upsert_user(user_id: int, username: str = "", first_name: str = "", last_name: str = "", referred_by: int = None):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        existing = conn.execute("SELECT total_starts FROM users WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            conn.execute("""
                UPDATE users SET username=?, first_name=?, last_name=?, last_seen=?,
                total_starts=total_starts+1 WHERE user_id=?
            """, (username or "", first_name or "", last_name or "", now, user_id))
        else:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, last_seen, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username or "", first_name or "", last_name or "", now, referred_by))
        conn.commit()
        return existing is None  # True = yeni kullanıcı


def set_user_member(user_id: int, is_member: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_member=? WHERE user_id=?", (1 if is_member else 0, user_id))
        conn.commit()


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def mark_reward_given(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET reward_given=1 WHERE user_id=?", (user_id,))
        conn.commit()


def search_users(query: str):
    with get_conn() as conn:
        q = f"%{query}%"
        return conn.execute(
            "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? OR CAST(user_id AS TEXT) LIKE ? LIMIT 10",
            (q, q, q)
        ).fetchall()


def ban_user(user_id: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=1, ban_reason=? WHERE user_id=?", (reason, user_id))
        conn.commit()


def unban_user(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=0, ban_reason='' WHERE user_id=?", (user_id,))
        conn.commit()


def get_user_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_member_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE is_member=1 AND is_banned=0").fetchone()[0]


def get_banned_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]


def get_today_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (f"{today}%",)).fetchone()[0]


def get_week_count() -> int:
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (week_ago,)).fetchone()[0]


def get_month_count() -> int:
    month_ago = (datetime.now() - timedelta(days=30)).isoformat()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (month_ago,)).fetchone()[0]


def get_all_user_ids(target: str = "all"):
    with get_conn() as conn:
        if target == "members":
            rows = conn.execute("SELECT user_id FROM users WHERE is_member=1 AND is_banned=0").fetchall()
        elif target == "nonmembers":
            rows = conn.execute("SELECT user_id FROM users WHERE is_member=0 AND is_banned=0").fetchall()
        else:
            rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
        return [r["user_id"] for r in rows]


def get_banned_users(limit=20):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE is_banned=1 ORDER BY user_id DESC LIMIT ?", (limit,)).fetchall()


def get_recent_users(limit=10):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY joined_at DESC LIMIT ?", (limit,)).fetchall()


# ─── Referral ────────────────────────────────────────────────

def add_referral(referrer_id: int, referred_id: int):
    """Yeni referans kaydı oluştur (henüz onaylanmadı)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (referrer_id, referred_id)
        )
        conn.commit()


def confirm_referral(referred_id: int) -> int | None:
    """Davet edilen kişi kanalları onaylayınca çağrılır. Referrer ID döner."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id=? AND channels_joined=0",
            (referred_id,)
        ).fetchone()
        if not row:
            return None
        referrer_id = row["referrer_id"]
        conn.execute(
            "UPDATE referrals SET channels_joined=1, confirmed_at=? WHERE referred_id=?",
            (datetime.now().isoformat(), referred_id)
        )
        conn.execute(
            "UPDATE users SET referral_count=referral_count+1 WHERE user_id=?",
            (referrer_id,)
        )
        conn.commit()
        return referrer_id


def get_referral_count(user_id: int) -> int:
    """Geçerli (kanalları onaylanmış) referans sayısı."""
    with get_conn() as conn:
        row = conn.execute("SELECT referral_count FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["referral_count"] if row else 0


def get_referral_details(user_id: int):
    """Referans listesi detayları."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT r.referred_id, r.channels_joined, r.created_at, r.confirmed_at,
                   u.first_name, u.username
            FROM referrals r
            LEFT JOIN users u ON u.user_id = r.referred_id
            WHERE r.referrer_id=?
            ORDER BY r.id DESC
        """, (user_id,)).fetchall()


def get_total_referral_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM referrals WHERE channels_joined=1").fetchone()[0]


# ─── Admins ──────────────────────────────────────────────────

def get_all_admins():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM admins ORDER BY added_at").fetchall()


def add_admin(user_id: int, added_by: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        conn.commit()


def remove_admin(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        conn.commit()


def is_admin_db(user_id: int, root_admin: int) -> bool:
    if user_id == root_admin:
        return True
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return row is not None


# ─── Broadcasts ──────────────────────────────────────────────

def save_broadcast(admin_id: int, message: str, target: str, sent: int, failed: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO broadcasts (admin_id, message, target, sent_count, failed_count) VALUES (?, ?, ?, ?, ?)",
            (admin_id, message, target, sent, failed)
        )
        conn.commit()


def get_broadcasts(limit=10):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get_broadcast_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM broadcasts").fetchone()[0]


# ─── Admin Logs ──────────────────────────────────────────────

def log_action(admin_id: int, action: str, detail: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_logs (admin_id, action, detail) VALUES (?, ?, ?)",
            (admin_id, action, detail)
        )
        conn.commit()


def get_recent_logs(limit=20):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


# ─── Reward Links ────────────────────────────────────────────

def get_active_reward_links():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM reward_links WHERE is_active=1 ORDER BY id").fetchall()


def get_all_reward_links():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM reward_links ORDER BY id").fetchall()


def add_reward_link(label: str, url: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO reward_links (label, url) VALUES (?, ?)", (label, url))
        conn.commit()


def remove_reward_link(link_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM reward_links WHERE id=?", (link_id,))
        conn.commit()


def toggle_reward_link(link_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE reward_links SET is_active = 1 - is_active WHERE id=?", (link_id,))
        conn.commit()
