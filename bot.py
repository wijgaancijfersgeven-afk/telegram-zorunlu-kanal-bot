import os
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from dotenv import load_dotenv
import database as db
import keyboards as kb

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8254024103"))

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN ayarlanmamış!")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
db.init_db()

BOT_START_TIME = time.time()

# ─── Yardımcılar ─────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return db.is_admin_db(user_id, ADMIN_ID)


def uptime_str() -> str:
    secs = int(time.time() - BOT_START_TIME)
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}g")
    if h: parts.append(f"{h}s")
    if m: parts.append(f"{m}dk")
    parts.append(f"{s}sn")
    return " ".join(parts)


def user_tag(user) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Kullanıcı"
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def check_membership(user_id: int):
    channels = db.get_all_channels()
    if not channels:
        return True, []
    not_joined = []
    for ch in channels:
        try:
            m = bot.get_chat_member(ch["channel_id"], user_id)
            if m.status in ("left", "kicked", "restricted"):
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined


# ─── Kullanıcı state ─────────────────────────────────────────

user_states: dict = {}

def set_state(uid: int, state: str, data: dict = None):
    user_states[uid] = {"state": state, "data": data or {}}

def get_state(uid: int) -> dict:
    return user_states.get(uid, {})

def clear_state(uid: int):
    user_states.pop(uid, None)


# ─── /start ──────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    user = msg.from_user
    db.upsert_user(user.id, user.username or "", user.first_name or "", user.last_name or "")
    clear_state(user.id)

    if get_setting_bool("maintenance_mode") and not is_admin(user.id):
        bot.send_message(msg.chat.id, db.get_setting("maintenance_message"))
        return

    if not get_setting_bool("bot_active") and not is_admin(user.id):
        bot.send_message(msg.chat.id, "🔴 Bot şu an aktif değil.")
        return

    channels = db.get_all_channels()
    force = get_setting_bool("force_join")

    if not channels or not force:
        send_reward(msg.chat.id, user)
        return

    all_ok, not_joined = check_membership(user.id)
    if all_ok:
        db.set_user_member(user.id, True)
        send_reward(msg.chat.id, user)
    else:
        db.set_user_member(user.id, False)
        welcome = db.get_setting("welcome_message").format(
            name=user.first_name or "Kullanıcı",
            id=user.id,
            username=user.username or ""
        )
        btn_text = db.get_setting("join_button_text") or "✅ Katıldım, Kontrol Et"
        bot.send_message(msg.chat.id, welcome, reply_markup=kb.join_keyboard(not_joined, btn_text))


def send_reward(chat_id: int, user):
    links = db.get_active_reward_links()
    success = db.get_setting("success_message")
    if links:
        bot.send_message(chat_id, success, reply_markup=kb.reward_keyboard(links))
    else:
        bot.send_message(chat_id, success)


def get_setting_bool(key: str) -> bool:
    return db.get_setting(key, "0") == "1"


# ─── Üyelik kontrol butonu ───────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "check_membership")
def cb_check(call):
    user = call.from_user
    user_row = db.get_user(user.id)
    if user_row and user_row["is_banned"]:
        bot.answer_callback_query(call.id, "🚫 Hesabınız yasaklandı.", show_alert=True)
        return

    all_ok, not_joined = check_membership(user.id)
    if all_ok:
        db.set_user_member(user.id, True)
        links = db.get_active_reward_links()
        success = db.get_setting("success_message")
        reward_kb = kb.reward_keyboard(links) if links else InlineKeyboardMarkup()
        try:
            bot.edit_message_text(success, call.message.chat.id, call.message.message_id,
                                  reply_markup=reward_kb, parse_mode="HTML")
        except Exception:
            bot.send_message(call.message.chat.id, success, reply_markup=reward_kb)
    else:
        pending = db.get_setting("pending_message")
        bot.answer_callback_query(call.id, pending.replace("<b>", "").replace("</b>", ""), show_alert=True)
        btn_text = db.get_setting("join_button_text") or "✅ Katıldım, Kontrol Et"
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=kb.join_keyboard(not_joined, btn_text))
        except Exception:
            pass


# ─── /admin ──────────────────────────────────────────────────

@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    if not is_admin(msg.from_user.id):
        return
    clear_state(msg.from_user.id)
    send_admin_panel(msg.chat.id, msg.message_id, edit=False)


def send_admin_panel(chat_id, message_id=None, edit=True):
    text = (
        "🛠 <b>Admin Paneli</b>\n\n"
        f"⏱ Uptime: <code>{uptime_str()}</code>\n"
        f"👥 Toplam kullanıcı: <b>{db.get_user_count()}</b>\n"
        f"✅ Üyeler: <b>{db.get_member_count()}</b>\n"
        f"🆕 Bugün: <b>{db.get_today_count()}</b>"
    )
    if edit and message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id,
                                  reply_markup=kb.admin_main_kb(), parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb.admin_main_kb())


# ─── Admin callback router ───────────────────────────────────

@bot.callback_query_handler(func=lambda c: (
    c.data.startswith("adm_") or c.data.startswith("ch_") or
    c.data.startswith("usr_") or c.data.startswith("bc_") or
    c.data.startswith("rw_") or c.data.startswith("msg_") or
    c.data.startswith("set_")
))
def cb_admin_router(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Yetkisiz!", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    data = call.data
    cid = call.message.chat.id
    mid = call.message.message_id
    uid = call.from_user.id

    # ── Ana menü ────────────────────────────────────────────

    if data == "adm_main":
        clear_state(uid)
        send_admin_panel(cid, mid)

    elif data == "adm_close":
        clear_state(uid)
        try:
            bot.delete_message(cid, mid)
        except Exception:
            pass

    # ── Kanal yönetimi ───────────────────────────────────────

    elif data == "adm_channels":
        channels = db.get_all_channels()
        if channels:
            text = "📢 <b>Mevcut Kanallar</b>\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. <b>{ch['channel_name'] or ch['channel_id']}</b>\n   ID: <code>{ch['channel_id']}</code>\n"
        else:
            text = "📢 <b>Henüz kanal eklenmedi.</b>\n\nBotu kanala admin olarak ekleyip kanal ID'sini girin."
        bot.edit_message_text(text, cid, mid, reply_markup=kb.channel_list_kb(channels), parse_mode="HTML")

    elif data == "ch_add":
        set_state(uid, "awaiting_channel")
        bot.send_message(cid,
            "📢 <b>Kanal Ekle</b>\n\n"
            "Kanal kullanıcı adı veya ID'sini gönder:\n"
            "• <code>@kanaladi</code>\n"
            "• <code>-1001234567890</code>\n\n"
            "⚠️ Botu kanala <b>admin</b> olarak eklemeyi unutma!", parse_mode="HTML")

    elif data.startswith("ch_del_"):
        channel_id = data[7:]
        db.remove_channel(channel_id)
        db.log_action(uid, "Kanal silindi", channel_id)
        channels = db.get_all_channels()
        text = "📢 <b>Kanal silindi!</b>\n\n"
        if channels:
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['channel_name'] or ch['channel_id']}\n"
        else:
            text += "Kanal kalmadı."
        bot.edit_message_text(text, cid, mid, reply_markup=kb.channel_list_kb(channels), parse_mode="HTML")

    # ── İstatistikler ────────────────────────────────────────

    elif data == "adm_stats":
        total = db.get_user_count()
        members = db.get_member_count()
        banned = db.get_banned_count()
        today = db.get_today_count()
        week = db.get_week_count()
        month = db.get_month_count()
        channels = db.get_all_channels()
        broadcasts = db.get_broadcast_count()
        pct = round(members / total * 100) if total else 0

        bar_filled = int(pct / 10)
        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)

        text = (
            f"📊 <b>Detaylı İstatistikler</b>\n\n"
            f"👥 <b>Kullanıcılar</b>\n"
            f"  Toplam: <b>{total}</b>\n"
            f"  Bugün katılan: <b>{today}</b>\n"
            f"  Bu hafta: <b>{week}</b>\n"
            f"  Bu ay: <b>{month}</b>\n"
            f"  Banlı: <b>{banned}</b>\n\n"
            f"✅ <b>Üyelik</b>\n"
            f"  Kanallara üye: <b>{members}</b> / {total}\n"
            f"  Oran: <b>%{pct}</b>\n"
            f"  {bar}\n\n"
            f"📢 Aktif kanal: <b>{len(channels)}</b>\n"
            f"📣 Toplam yayın: <b>{broadcasts}</b>\n"
            f"⏱ Uptime: <code>{uptime_str()}</code>"
        )
        stat_kb = InlineKeyboardMarkup()
        stat_kb.add(InlineKeyboardButton("🔄 Yenile", callback_data="adm_stats"))
        stat_kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
        bot.edit_message_text(text, cid, mid, reply_markup=stat_kb, parse_mode="HTML")

    # ── Kullanıcı yönetimi ───────────────────────────────────

    elif data == "adm_users":
        bot.edit_message_text("👥 <b>Kullanıcı Yönetimi</b>", cid, mid,
                              reply_markup=kb.users_menu_kb(), parse_mode="HTML")

    elif data == "usr_search":
        set_state(uid, "user_search")
        bot.send_message(cid,
            "🔍 <b>Kullanıcı Ara</b>\n\n"
            "Kullanıcı adı, isim veya Telegram ID gönder:", parse_mode="HTML")

    elif data == "usr_recent":
        users = db.get_recent_users(10)
        text = "🆕 <b>Son 10 Kullanıcı</b>\n\n"
        for u in users:
            name = u["first_name"] or "—"
            uname = f"@{u['username']}" if u["username"] else f"#{u['user_id']}"
            status = "✅" if u["is_member"] else "❌"
            ban = " 🚫" if u["is_banned"] else ""
            text += f"{status}{ban} <code>{u['user_id']}</code> — {name} ({uname})\n"
        recent_kb = InlineKeyboardMarkup()
        recent_kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_users"))
        bot.edit_message_text(text, cid, mid, reply_markup=recent_kb, parse_mode="HTML")

    elif data == "usr_banned":
        banned = db.get_banned_users(20)
        if banned:
            text = "🚫 <b>Banlı Kullanıcılar</b>\n\n"
            for u in banned:
                reason = u["ban_reason"] or "—"
                text += f"• <code>{u['user_id']}</code> — {u['first_name'] or '?'} | Sebep: {reason}\n"
        else:
            text = "✅ Banlı kullanıcı yok."
        banned_kb = InlineKeyboardMarkup()
        banned_kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_users"))
        bot.edit_message_text(text, cid, mid, reply_markup=banned_kb, parse_mode="HTML")

    elif data.startswith("usr_ban_"):
        target_id = int(data[8:])
        set_state(uid, "ban_reason", {"target_id": target_id})
        bot.send_message(cid,
            f"🚫 <b>Ban Sebebi</b>\n\n<code>{target_id}</code> için ban sebebini yaz\n(Yok ise - yaz):",
            parse_mode="HTML")

    elif data.startswith("usr_unban_"):
        target_id = int(data[10:])
        db.unban_user(target_id)
        db.log_action(uid, "Kullanıcı ban kaldırıldı", str(target_id))
        bot.send_message(cid, f"✅ <code>{target_id}</code> kullanıcısının banı kaldırıldı.", parse_mode="HTML")
        try:
            bot.send_message(target_id, "✅ Hesabınızın yasağı kaldırıldı. /start yazabilirsiniz.")
        except Exception:
            pass

    elif data.startswith("usr_msg_"):
        target_id = int(data[8:])
        set_state(uid, "send_user_msg", {"target_id": target_id})
        bot.send_message(cid,
            f"📨 <code>{target_id}</code> kullanıcısına gönderilecek mesajı yaz:", parse_mode="HTML")

    # ── Yayın ────────────────────────────────────────────────

    elif data == "adm_broadcast":
        bot.edit_message_text(
            "📣 <b>Yayın Gönder</b>\n\nKime göndermek istiyorsun?",
            cid, mid, reply_markup=kb.broadcast_target_kb(), parse_mode="HTML")

    elif data in ("bc_all", "bc_members", "bc_nonmembers"):
        target = data[3:]
        labels = {"all": "Herkese", "members": "Üyelere", "nonmembers": "Üye Olmayanlara"}
        set_state(uid, "awaiting_broadcast", {"target": target})
        bot.edit_message_text(
            f"📣 <b>{labels[target]} Yayın</b>\n\nGönderilecek mesajı yaz:",
            cid, mid, reply_markup=kb.back_kb("adm_broadcast"), parse_mode="HTML")

    elif data.startswith("bc_confirm_"):
        target = data[11:]
        state = get_state(uid)
        msg_text = state.get("data", {}).get("msg_text", "")
        if not msg_text:
            bot.send_message(cid, "❌ Mesaj bulunamadı. Tekrar dene.")
            return
        clear_state(uid)
        user_ids = db.get_all_user_ids(target)
        total = len(user_ids)
        sent = failed = 0
        progress_msg = bot.send_message(cid, f"⏳ Gönderiliyor... 0/{total}")
        for i, uid_target in enumerate(user_ids):
            try:
                bot.send_message(uid_target, msg_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
            if (i + 1) % 20 == 0:
                try:
                    bot.edit_message_text(
                        f"⏳ Gönderiliyor... {i+1}/{total}",
                        cid, progress_msg.message_id)
                except Exception:
                    pass
        db.save_broadcast(uid, msg_text, target, sent, failed)
        db.log_action(uid, "Yayın gönderildi", f"Hedef:{target} Gönderilen:{sent} Başarısız:{failed}")
        bot.edit_message_text(
            f"📣 <b>Yayın Tamamlandı!</b>\n\n"
            f"✅ Gönderildi: <b>{sent}</b>\n"
            f"❌ Başarısız: <b>{failed}</b>\n"
            f"👥 Toplam: <b>{total}</b>",
            cid, progress_msg.message_id, parse_mode="HTML")

    # ── Yayın geçmişi ────────────────────────────────────────

    elif data == "adm_broadcast_history":
        broadcasts = db.get_broadcasts(10)
        if broadcasts:
            text = "📜 <b>Son 10 Yayın</b>\n\n"
            targets = {"all": "Herkese", "members": "Üyelere", "nonmembers": "Üye Olmayanlara"}
            for b in broadcasts:
                preview = b["message"][:40].replace("\n", " ") + "..."
                text += (
                    f"📣 <i>{b['sent_at'][:16]}</i> — {targets.get(b['target'], b['target'])}\n"
                    f"   ✅{b['sent_count']} ❌{b['failed_count']} | <i>{preview}</i>\n\n"
                )
        else:
            text = "📜 Henüz yayın yapılmadı."
        hist_kb = InlineKeyboardMarkup()
        hist_kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
        bot.edit_message_text(text, cid, mid, reply_markup=hist_kb, parse_mode="HTML")

    # ── Ödül linkleri ────────────────────────────────────────

    elif data == "adm_rewards":
        links = db.get_all_reward_links()
        text = "🔗 <b>Ödül Linkleri</b>\n\n"
        if links:
            for lnk in links:
                s = "✅" if lnk["is_active"] else "❌"
                text += f"{s} <b>{lnk['label']}</b>\n   <code>{lnk['url']}</code>\n\n"
        else:
            text += "Henüz link eklenmedi."
        bot.edit_message_text(text, cid, mid, reply_markup=kb.reward_mgmt_kb(links), parse_mode="HTML")

    elif data == "rw_add":
        set_state(uid, "awaiting_reward_label")
        bot.send_message(cid, "🔗 <b>Yeni Link Ekle</b>\n\nÖnce linkin <b>etiketini</b> yaz (örn: Ana Grup):", parse_mode="HTML")

    elif data.startswith("rw_toggle_"):
        link_id = int(data[10:])
        db.toggle_reward_link(link_id)
        db.log_action(uid, "Ödül linki değiştirildi", str(link_id))
        links = db.get_all_reward_links()
        text = "🔗 <b>Ödül Linkleri güncellendi.</b>"
        bot.edit_message_text(text, cid, mid, reply_markup=kb.reward_mgmt_kb(links), parse_mode="HTML")

    elif data.startswith("rw_del_"):
        link_id = int(data[7:])
        db.remove_reward_link(link_id)
        db.log_action(uid, "Ödül linki silindi", str(link_id))
        links = db.get_all_reward_links()
        bot.edit_message_text("🔗 <b>Link silindi.</b>", cid, mid,
                              reply_markup=kb.reward_mgmt_kb(links), parse_mode="HTML")

    # ── Mesaj düzenleme ──────────────────────────────────────

    elif data == "adm_messages":
        bot.edit_message_text("✏️ <b>Mesaj Düzenleme</b>", cid, mid,
                              reply_markup=kb.messages_kb(), parse_mode="HTML")

    elif data == "msg_welcome":
        cur = db.get_setting("welcome_message")
        set_state(uid, "edit_msg", {"key": "welcome_message"})
        bot.send_message(cid,
            f"📝 <b>Karşılama Mesajı</b>\n\nMevcut:\n<i>{cur}</i>\n\n"
            "Yeni mesajı yaz. Kullanılabilir: <code>{name}</code> <code>{id}</code> <code>{username}</code>",
            parse_mode="HTML")

    elif data == "msg_success":
        cur = db.get_setting("success_message")
        set_state(uid, "edit_msg", {"key": "success_message"})
        bot.send_message(cid, f"✅ <b>Başarı Mesajı</b>\n\nMevcut:\n<i>{cur}</i>\n\nYeni mesajı yaz:", parse_mode="HTML")

    elif data == "msg_pending":
        cur = db.get_setting("pending_message")
        set_state(uid, "edit_msg", {"key": "pending_message"})
        bot.send_message(cid, f"⏳ <b>Bekleme Mesajı</b>\n\nMevcut:\n<i>{cur}</i>\n\nYeni mesajı yaz:", parse_mode="HTML")

    elif data == "msg_btntext":
        cur = db.get_setting("join_button_text")
        set_state(uid, "edit_msg", {"key": "join_button_text"})
        bot.send_message(cid, f"🔘 <b>Buton Yazısı</b>\n\nMevcut: <i>{cur}</i>\n\nYeni yazıyı yaz:", parse_mode="HTML")

    # ── Admin yönetimi ───────────────────────────────────────

    elif data == "adm_admins":
        admins = db.get_all_admins()
        text = f"👑 <b>Admin Listesi</b>\n\n🔴 Root Admin: <code>{ADMIN_ID}</code>\n\n"
        if admins:
            for a in admins:
                text += f"• <code>{a['user_id']}</code> — Eklendi: {a['added_at'][:10]}\n"
        else:
            text += "Başka admin yok."
        bot.edit_message_text(text, cid, mid, reply_markup=kb.admins_kb(admins), parse_mode="HTML")

    elif data == "adm_add":
        set_state(uid, "awaiting_admin_id")
        bot.send_message(cid, "👑 <b>Admin Ekle</b>\n\nYeni adminin Telegram ID'sini gönder:", parse_mode="HTML")

    elif data.startswith("adm_del_"):
        target_id = int(data[8:])
        if target_id == ADMIN_ID:
            bot.send_message(cid, "❌ Root admin silinemez!")
            return
        db.remove_admin(target_id)
        db.log_action(uid, "Admin silindi", str(target_id))
        admins = db.get_all_admins()
        bot.edit_message_text("✅ Admin silindi.", cid, mid,
                              reply_markup=kb.admins_kb(admins), parse_mode="HTML")

    # ── Bot ayarları ─────────────────────────────────────────

    elif data == "adm_settings":
        maintenance = get_setting_bool("maintenance_mode")
        force_join = get_setting_bool("force_join")
        bot_active = get_setting_bool("bot_active")
        text = (
            "⚙️ <b>Bot Ayarları</b>\n\n"
            f"🔧 Bakım Modu: {'AÇIK' if maintenance else 'KAPALI'}\n"
            f"🔒 Zorunlu Üyelik: {'AÇIK' if force_join else 'KAPALI'}\n"
            f"🤖 Bot: {'AKTİF' if bot_active else 'PASİF'}"
        )
        bot.edit_message_text(text, cid, mid,
                              reply_markup=kb.settings_kb(maintenance, force_join, bot_active),
                              parse_mode="HTML")

    elif data == "set_maintenance":
        val = "0" if get_setting_bool("maintenance_mode") else "1"
        db.set_setting("maintenance_mode", val)
        db.log_action(uid, "Bakım modu", "Açıldı" if val == "1" else "Kapatıldı")
        maintenance = val == "1"
        force_join = get_setting_bool("force_join")
        bot_active = get_setting_bool("bot_active")
        text = (
            "⚙️ <b>Bot Ayarları</b>\n\n"
            f"🔧 Bakım Modu: {'AÇIK' if maintenance else 'KAPALI'}\n"
            f"🔒 Zorunlu Üyelik: {'AÇIK' if force_join else 'KAPALI'}\n"
            f"🤖 Bot: {'AKTİF' if bot_active else 'PASİF'}"
        )
        bot.edit_message_text(text, cid, mid,
                              reply_markup=kb.settings_kb(maintenance, force_join, bot_active),
                              parse_mode="HTML")

    elif data == "set_forcejoin":
        val = "0" if get_setting_bool("force_join") else "1"
        db.set_setting("force_join", val)
        db.log_action(uid, "Zorunlu üyelik", "Açıldı" if val == "1" else "Kapatıldı")
        maintenance = get_setting_bool("maintenance_mode")
        force_join = val == "1"
        bot_active = get_setting_bool("bot_active")
        text = (
            "⚙️ <b>Bot Ayarları</b>\n\n"
            f"🔧 Bakım Modu: {'AÇIK' if maintenance else 'KAPALI'}\n"
            f"🔒 Zorunlu Üyelik: {'AÇIK' if force_join else 'KAPALI'}\n"
            f"🤖 Bot: {'AKTİF' if bot_active else 'PASİF'}"
        )
        bot.edit_message_text(text, cid, mid,
                              reply_markup=kb.settings_kb(maintenance, force_join, bot_active),
                              parse_mode="HTML")

    elif data == "set_botactive":
        val = "0" if get_setting_bool("bot_active") else "1"
        db.set_setting("bot_active", val)
        db.log_action(uid, "Bot aktiflik", "Açıldı" if val == "1" else "Kapatıldı")
        maintenance = get_setting_bool("maintenance_mode")
        force_join = get_setting_bool("force_join")
        bot_active = val == "1"
        text = (
            "⚙️ <b>Bot Ayarları</b>\n\n"
            f"🔧 Bakım Modu: {'AÇIK' if maintenance else 'KAPALI'}\n"
            f"🔒 Zorunlu Üyelik: {'AÇIK' if force_join else 'KAPALI'}\n"
            f"🤖 Bot: {'AKTİF' if bot_active else 'PASİF'}"
        )
        bot.edit_message_text(text, cid, mid,
                              reply_markup=kb.settings_kb(maintenance, force_join, bot_active),
                              parse_mode="HTML")

    elif data == "set_maintenancemsg":
        cur = db.get_setting("maintenance_message")
        set_state(uid, "edit_msg", {"key": "maintenance_message"})
        bot.send_message(cid, f"🔧 <b>Bakım Mesajı</b>\n\nMevcut:\n<i>{cur}</i>\n\nYeni mesajı yaz:", parse_mode="HTML")

    # ── Admin logları ────────────────────────────────────────

    elif data == "adm_logs":
        logs = db.get_recent_logs(20)
        if logs:
            text = "📋 <b>Son 20 Admin İşlemi</b>\n\n"
            for log in logs:
                text += f"• [{log['created_at'][11:16]}] <code>{log['admin_id']}</code> — {log['action']}"
                if log["detail"]:
                    text += f" <i>({log['detail']})</i>"
                text += "\n"
        else:
            text = "📋 Henüz log kaydı yok."
        log_kb = InlineKeyboardMarkup()
        log_kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
        bot.edit_message_text(text, cid, mid, reply_markup=log_kb, parse_mode="HTML")


# ─── Metin state machine ─────────────────────────────────────

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    if msg.text.startswith("/"):
        return
    uid = msg.from_user.id
    si = get_state(uid)
    state = si.get("state")
    data = si.get("data", {})
    text = msg.text.strip()
    cid = msg.chat.id

    # Herkes

    if state == "awaiting_channel" and is_admin(uid):
        clear_state(uid)
        channel_id = text if text.startswith("-") else f"@{text.lstrip('@')}"
        try:
            chat = bot.get_chat(channel_id)
            name = chat.title or channel_id
            invite = ""
            try:
                invite = chat.invite_link or bot.export_chat_invite_link(channel_id)
            except Exception:
                pass
            db.add_channel(channel_id, name, invite)
            db.log_action(uid, "Kanal eklendi", f"{name} ({channel_id})")
            bot.send_message(cid,
                f"✅ <b>Kanal eklendi!</b>\n\n"
                f"📢 <b>{name}</b>\n"
                f"ID: <code>{channel_id}</code>\n\n"
                f"/admin ile panele dön.", parse_mode="HTML")
        except Exception as e:
            bot.send_message(cid,
                f"❌ Kanal bulunamadı veya bot admin değil!\n"
                f"Hata: <code>{e}</code>", parse_mode="HTML")

    elif state == "awaiting_broadcast" and is_admin(uid):
        target = data.get("target", "all")
        set_state(uid, "broadcast_confirm", {"target": target, "msg_text": text})
        count = len(db.get_all_user_ids(target))
        labels = {"all": "Herkes", "members": "Üyeler", "nonmembers": "Üye olmayanlar"}
        bot.send_message(cid,
            f"📣 <b>Yayın Önizleme</b>\n\n{text}\n\n"
            f"─────────────\n"
            f"🎯 Hedef: <b>{labels.get(target, target)}</b>\n"
            f"👥 Kişi sayısı: <b>{count}</b>\n\n"
            f"Onaylıyor musun?",
            reply_markup=kb.broadcast_confirm_kb(target), parse_mode="HTML")

    elif state == "broadcast_confirm" and is_admin(uid):
        pass

    elif state == "edit_msg" and is_admin(uid):
        key = data.get("key")
        clear_state(uid)
        db.set_setting(key, text)
        db.log_action(uid, "Mesaj güncellendi", key)
        bot.send_message(cid, f"✅ <b>Güncellendi!</b>\n\n/admin ile panele dön.", parse_mode="HTML")

    elif state == "awaiting_reward_label" and is_admin(uid):
        set_state(uid, "awaiting_reward_url", {"label": text})
        bot.send_message(cid, f"🔗 Etiket: <b>{text}</b>\n\nŞimdi linki gönder (https://...):", parse_mode="HTML")

    elif state == "awaiting_reward_url" and is_admin(uid):
        label = data.get("label", "Link")
        clear_state(uid)
        db.add_reward_link(label, text)
        db.log_action(uid, "Ödül linki eklendi", f"{label}: {text}")
        bot.send_message(cid, f"✅ <b>Link eklendi!</b>\n\n{label}: <code>{text}</code>\n\n/admin ile panele dön.", parse_mode="HTML")

    elif state == "awaiting_admin_id" and is_admin(uid):
        clear_state(uid)
        try:
            new_admin_id = int(text)
            db.add_admin(new_admin_id, uid)
            db.log_action(uid, "Admin eklendi", str(new_admin_id))
            bot.send_message(cid, f"✅ <code>{new_admin_id}</code> admin olarak eklendi!", parse_mode="HTML")
            try:
                bot.send_message(new_admin_id, f"👑 Siz admin olarak eklendini! /admin komutunu kullanabilirsiniz.")
            except Exception:
                pass
        except ValueError:
            bot.send_message(cid, "❌ Geçerli bir Telegram ID girin (sadece rakam).")

    elif state == "user_search" and is_admin(uid):
        clear_state(uid)
        results = db.search_users(text)
        if not results:
            bot.send_message(cid, "🔍 Kullanıcı bulunamadı.")
            return
        for u in results:
            name = f"{u['first_name'] or ''} {u.get('last_name', '') or ''}".strip() or "—"
            uname = f"@{u['username']}" if u["username"] else "—"
            status = "✅ Üye" if u["is_member"] else "❌ Üye Değil"
            banned = " | 🚫 Banlı" if u["is_banned"] else ""
            text_msg = (
                f"👤 <b>Kullanıcı Detayı</b>\n\n"
                f"🆔 ID: <code>{u['user_id']}</code>\n"
                f"📛 Ad: {name}\n"
                f"🔖 Kullanıcı adı: {uname}\n"
                f"📊 Durum: {status}{banned}\n"
                f"🔢 Toplam başlatma: {u['total_starts']}\n"
                f"📅 Katıldı: {(u['joined_at'] or '')[:16]}\n"
                f"🕐 Son görülme: {(u['last_seen'] or '')[:16]}"
            )
            bot.send_message(cid, text_msg,
                             reply_markup=kb.user_detail_kb(u["user_id"], bool(u["is_banned"])),
                             parse_mode="HTML")

    elif state == "ban_reason" and is_admin(uid):
        target_id = data.get("target_id")
        reason = "" if text == "-" else text
        clear_state(uid)
        db.ban_user(target_id, reason)
        db.log_action(uid, "Kullanıcı banlı", f"{target_id} - {reason}")
        bot.send_message(cid, f"🚫 <code>{target_id}</code> banlandı.\nSebep: {reason or '—'}", parse_mode="HTML")
        try:
            bot.send_message(target_id, f"🚫 Hesabınız yasaklandı.\nSebep: {reason or '—'}")
        except Exception:
            pass

    elif state == "send_user_msg" and is_admin(uid):
        target_id = data.get("target_id")
        clear_state(uid)
        try:
            bot.send_message(target_id, f"📨 <b>Admin mesajı:</b>\n\n{text}", parse_mode="HTML")
            bot.send_message(cid, f"✅ Mesaj <code>{target_id}</code> kullanıcısına gönderildi.", parse_mode="HTML")
        except Exception as e:
            bot.send_message(cid, f"❌ Gönderilemedi: {e}")


# ─── Başlatma ────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Zorunlu Kanal Bot başlatıldı...")
    try:
        bot.set_my_commands([
            BotCommand("start", "Botu başlat"),
            BotCommand("admin", "Admin paneli"),
        ])
    except Exception:
        pass
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
