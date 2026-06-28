import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import database as db

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8254024103"))

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN ayarlanmamış!")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
db.init_db()

# ─── Yardımcı ────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def check_membership(user_id: int) -> tuple[bool, list]:
    channels = db.get_all_channels()
    if not channels:
        return True, []
    not_joined = []
    for ch in channels:
        try:
            member = bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked", "restricted"):
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined


def join_keyboard(not_joined: list, show_check=True) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in not_joined:
        name = ch["channel_name"] or ch["channel_id"]
        link = ch["invite_link"] or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        kb.add(InlineKeyboardButton(f"📢 {name}", url=link))
    if show_check:
        kb.add(InlineKeyboardButton("✅ Katıldım, kontrol et", callback_data="check_membership"))
    return kb


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📢 Kanallar", callback_data="admin_channels"),
        InlineKeyboardButton("🔗 Ödül Linki", callback_data="admin_reward"),
    )
    kb.add(
        InlineKeyboardButton("📝 Karşılama Mesajı", callback_data="admin_welcome"),
        InlineKeyboardButton("✅ Başarı Mesajı", callback_data="admin_success"),
    )
    kb.add(
        InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        InlineKeyboardButton("📣 Yayın Gönder", callback_data="admin_broadcast"),
    )
    kb.add(InlineKeyboardButton("❌ Kapat", callback_data="admin_close"))
    return kb


def channel_list_keyboard(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        name = ch["channel_name"] or ch["channel_id"]
        kb.add(InlineKeyboardButton(f"🗑 {name} — sil", callback_data=f"del_ch_{ch['channel_id']}"))
    kb.add(InlineKeyboardButton("➕ Kanal Ekle", callback_data="add_channel"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="admin_back"))
    return kb


# ─── Kullanıcı durumu (bekleme) ──────────────────────────────

user_states = {}

def set_state(user_id: int, state: str, data: dict = None):
    user_states[user_id] = {"state": state, "data": data or {}}

def get_state(user_id: int):
    return user_states.get(user_id, {})

def clear_state(user_id: int):
    user_states.pop(user_id, None)


# ─── /start ──────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    user = msg.from_user
    db.upsert_user(user.id, user.username or "", user.first_name or "")
    clear_state(user.id)

    channels = db.get_all_channels()
    if not channels:
        welcome = db.get_setting("welcome_message").format(name=user.first_name or "Kullanıcı")
        success = db.get_setting("success_message")
        reward = db.get_setting("reward_link")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔗 Özel Link", url=reward))
        bot.send_message(msg.chat.id,
            f"{welcome}\n\n{success}\n\n<b>{reward}</b>",
            reply_markup=kb)
        return

    all_joined, not_joined = check_membership(user.id)

    if all_joined:
        db.set_user_member(user.id, True)
        reward = db.get_setting("reward_link")
        success_msg = db.get_setting("success_message")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔗 Özel Linke Git", url=reward))
        bot.send_message(msg.chat.id, f"{success_msg}\n\n<b>{reward}</b>", reply_markup=kb)
    else:
        db.set_user_member(user.id, False)
        welcome = db.get_setting("welcome_message").format(name=user.first_name or "Kullanıcı")
        bot.send_message(msg.chat.id, welcome, reply_markup=join_keyboard(not_joined))


# ─── Üyelik kontrol butonu ───────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "check_membership")
def cb_check(call):
    user = call.from_user
    db.upsert_user(user.id, user.username or "", user.first_name or "")

    all_joined, not_joined = check_membership(user.id)

    if all_joined:
        db.set_user_member(user.id, True)
        reward = db.get_setting("reward_link")
        success_msg = db.get_setting("success_message")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔗 Özel Linke Git", url=reward))
        bot.edit_message_text(
            f"{success_msg}\n\n<b>{reward}</b>",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Henüz tüm kanallara katılmadın!", show_alert=True)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id,
                reply_markup=join_keyboard(not_joined)
            )
        except Exception:
            pass


# ─── /admin ──────────────────────────────────────────────────

@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    if not is_admin(msg.from_user.id):
        bot.send_message(msg.chat.id, "⛔ Bu komut sadece admin içindir.")
        return
    clear_state(msg.from_user.id)
    bot.send_message(msg.chat.id,
        "🛠 <b>Admin Paneli</b>\n\nAşağıdan bir işlem seç:",
        reply_markup=admin_panel_keyboard()
    )


# ─── Admin callback'leri ─────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_") or c.data.startswith("del_ch_") or c.data in ("add_channel",))
def cb_admin(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Yetkisiz!", show_alert=True)
        return

    data = call.data
    cid = call.message.chat.id
    mid = call.message.message_id

    if data == "admin_back":
        clear_state(call.from_user.id)
        bot.edit_message_text("🛠 <b>Admin Paneli</b>\n\nAşağıdan bir işlem seç:",
            cid, mid, reply_markup=admin_panel_keyboard(), parse_mode="HTML")

    elif data == "admin_close":
        clear_state(call.from_user.id)
        bot.delete_message(cid, mid)
        bot.answer_callback_query(call.id)

    elif data == "admin_channels":
        channels = db.get_all_channels()
        if channels:
            text = "📢 <b>Mevcut Kanallar:</b>\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['channel_name'] or ch['channel_id']} (<code>{ch['channel_id']}</code>)\n"
        else:
            text = "📢 <b>Henüz kanal eklenmedi.</b>"
        bot.edit_message_text(text, cid, mid,
            reply_markup=channel_list_keyboard(channels), parse_mode="HTML")

    elif data == "add_channel":
        set_state(call.from_user.id, "awaiting_channel_id")
        bot.answer_callback_query(call.id)
        bot.send_message(cid,
            "📢 <b>Kanal Ekle</b>\n\nKanalın kullanıcı adını veya ID'sini gönder.\n"
            "Örnek: <code>@kanaladi</code> veya <code>-1001234567890</code>\n\n"
            "⚠️ Botu kanala admin olarak eklemeyi unutma!",
            parse_mode="HTML"
        )

    elif data.startswith("del_ch_"):
        channel_id = data[7:]
        db.remove_channel(channel_id)
        channels = db.get_all_channels()
        text = "📢 <b>Kanal silindi.</b>\n\n"
        if channels:
            text += "Mevcut kanallar:\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['channel_name'] or ch['channel_id']}\n"
        else:
            text += "Henüz kanal yok."
        bot.edit_message_text(text, cid, mid,
            reply_markup=channel_list_keyboard(channels), parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ Kanal silindi!")

    elif data == "admin_reward":
        current = db.get_setting("reward_link")
        set_state(call.from_user.id, "awaiting_reward_link")
        bot.answer_callback_query(call.id)
        bot.send_message(cid,
            f"🔗 <b>Ödül Linki Güncelle</b>\n\nMevcut link:\n<code>{current}</code>\n\nYeni linki gönder:",
            parse_mode="HTML"
        )

    elif data == "admin_welcome":
        current = db.get_setting("welcome_message")
        set_state(call.from_user.id, "awaiting_welcome_msg")
        bot.answer_callback_query(call.id)
        bot.send_message(cid,
            f"📝 <b>Karşılama Mesajı Güncelle</b>\n\nMevcut:\n<i>{current}</i>\n\n"
            "Yeni mesajı gönder.\n💡 <code>{{name}}</code> kullanıcı adı için kullanılır.",
            parse_mode="HTML"
        )

    elif data == "admin_success":
        current = db.get_setting("success_message")
        set_state(call.from_user.id, "awaiting_success_msg")
        bot.answer_callback_query(call.id)
        bot.send_message(cid,
            f"✅ <b>Başarı Mesajı Güncelle</b>\n\nMevcut:\n<i>{current}</i>\n\nYeni mesajı gönder:",
            parse_mode="HTML"
        )

    elif data == "admin_stats":
        total = db.get_user_count()
        members = db.get_member_count()
        channels = db.get_all_channels()
        broadcasts = db.get_broadcast_count()
        text = (
            f"📊 <b>İstatistikler</b>\n\n"
            f"👥 Toplam kullanıcı: <b>{total}</b>\n"
            f"✅ Tüm kanallara üye: <b>{members}</b>\n"
            f"📢 Kanal sayısı: <b>{len(channels)}</b>\n"
            f"📣 Yapılan yayın: <b>{broadcasts}</b>"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("◀️ Geri", callback_data="admin_back"))
        bot.edit_message_text(text, cid, mid, reply_markup=kb, parse_mode="HTML")

    elif data == "admin_broadcast":
        set_state(call.from_user.id, "awaiting_broadcast")
        bot.answer_callback_query(call.id)
        bot.send_message(cid,
            "📣 <b>Yayın Gönder</b>\n\nTüm kullanıcılara gönderilecek mesajı yaz:\n\n"
            "İptal için /admin yaz.",
            parse_mode="HTML"
        )


# ─── Metin mesajları (state machine) ─────────────────────────

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    if msg.text.startswith("/"):
        return

    uid = msg.from_user.id
    state_info = get_state(uid)
    state = state_info.get("state")

    if not state:
        return

    if not is_admin(uid) and state.startswith("awaiting_"):
        return

    text = msg.text.strip()

    if state == "awaiting_channel_id":
        clear_state(uid)
        channel_id = text if text.startswith("-") else f"@{text.lstrip('@')}"
        try:
            chat = bot.get_chat(channel_id)
            name = chat.title or channel_id
            invite_link = ""
            try:
                invite_link = chat.invite_link or bot.export_chat_invite_link(channel_id)
            except Exception:
                pass
            db.add_channel(channel_id, name, invite_link)
            bot.send_message(msg.chat.id,
                f"✅ Kanal eklendi!\n\n<b>{name}</b> (<code>{channel_id}</code>)\n\n"
                f"Admin paneli için /admin",
                parse_mode="HTML"
            )
        except Exception as e:
            bot.send_message(msg.chat.id,
                f"❌ Kanal bulunamadı veya bot admin değil!\n\nHata: <code>{e}</code>\n\n"
                "Bot'u kanala admin olarak ekleyip tekrar dene.",
                parse_mode="HTML"
            )

    elif state == "awaiting_reward_link":
        clear_state(uid)
        db.set_setting("reward_link", text)
        bot.send_message(msg.chat.id,
            f"✅ Ödül linki güncellendi!\n\n<code>{text}</code>\n\nAdmin paneli için /admin",
            parse_mode="HTML"
        )

    elif state == "awaiting_welcome_msg":
        clear_state(uid)
        db.set_setting("welcome_message", text)
        bot.send_message(msg.chat.id,
            f"✅ Karşılama mesajı güncellendi!\n\nAdmin paneli için /admin",
            parse_mode="HTML"
        )

    elif state == "awaiting_success_msg":
        clear_state(uid)
        db.set_setting("success_message", text)
        bot.send_message(msg.chat.id,
            f"✅ Başarı mesajı güncellendi!\n\nAdmin paneli için /admin",
            parse_mode="HTML"
        )

    elif state == "awaiting_broadcast":
        clear_state(uid)
        user_ids = db.get_all_user_ids()
        sent = 0
        failed = 0
        for user_id in user_ids:
            try:
                bot.send_message(user_id, text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        db.save_broadcast(text, sent)
        bot.send_message(msg.chat.id,
            f"📣 <b>Yayın tamamlandı!</b>\n\n✅ Gönderildi: <b>{sent}</b>\n❌ Başarısız: <b>{failed}</b>",
            parse_mode="HTML"
        )


# ─── Başlatma ────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Zorunlu Kanal Bot başlatıldı...")
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "Botu başlat"),
            telebot.types.BotCommand("admin", "Admin paneli"),
        ])
    except Exception:
        pass
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
