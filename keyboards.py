from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def join_keyboard(not_joined: list, btn_text: str = "✅ Katıldım, Kontrol Et") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in not_joined:
        name = ch["channel_name"] or ch["channel_id"]
        link = ch["invite_link"] or f"https://t.me/{ch['channel_id'].lstrip('@')}"
        kb.add(InlineKeyboardButton(f"📢 {name}", url=link))
    kb.add(InlineKeyboardButton(btn_text, callback_data="check_membership"))
    return kb


def referral_keyboard(ref_link: str, count: int, required: int) -> InlineKeyboardMarkup:
    remaining = required - count
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"📊 Referanslarım ({count}/{required})", callback_data="ref_status"))
    kb.add(InlineKeyboardButton("🔗 Davet Linkimi Kopyala", switch_inline_query=ref_link))
    kb.add(InlineKeyboardButton(f"⏳ {remaining} kişi daha davet et", callback_data="ref_status"))
    return kb


def reward_keyboard(links: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for lnk in links:
        kb.add(InlineKeyboardButton(f"🔗 {lnk['label']}", url=lnk["url"]))
    return kb


def ref_status_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔄 Yenile", callback_data="ref_status"))
    kb.add(InlineKeyboardButton("🔗 Davet Linkimi Gör", callback_data="ref_link"))
    return kb


# ─── Admin Ana Menü ──────────────────────────────────────────

def admin_main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📢 Kanal Yönetimi", callback_data="adm_channels"),
        InlineKeyboardButton("👥 Kullanıcılar", callback_data="adm_users"),
    )
    kb.add(
        InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats"),
        InlineKeyboardButton("📣 Yayın Gönder", callback_data="adm_broadcast"),
    )
    kb.add(
        InlineKeyboardButton("🔗 Ödül Linkleri", callback_data="adm_rewards"),
        InlineKeyboardButton("✏️ Mesajlar", callback_data="adm_messages"),
    )
    kb.add(
        InlineKeyboardButton("👑 Admin Yönetimi", callback_data="adm_admins"),
        InlineKeyboardButton("⚙️ Bot Ayarları", callback_data="adm_settings"),
    )
    kb.add(
        InlineKeyboardButton("📋 Admin Logları", callback_data="adm_logs"),
        InlineKeyboardButton("📜 Yayın Geçmişi", callback_data="adm_broadcast_history"),
    )
    kb.add(InlineKeyboardButton("❌ Kapat", callback_data="adm_close"))
    return kb


def back_kb(target: str = "adm_main") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data=target))
    return kb


def channel_list_kb(channels) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        name = ch["channel_name"] or ch["channel_id"]
        kb.add(InlineKeyboardButton(f"🗑 {name}", callback_data=f"ch_del_{ch['channel_id']}"))
    kb.add(InlineKeyboardButton("➕ Kanal Ekle", callback_data="ch_add"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def users_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔍 Kullanıcı Ara", callback_data="usr_search"),
        InlineKeyboardButton("🆕 Son Üyeler", callback_data="usr_recent"),
    )
    kb.add(
        InlineKeyboardButton("🚫 Banlı Kullanıcılar", callback_data="usr_banned"),
        InlineKeyboardButton("🏆 En Çok Davet Eden", callback_data="usr_toprefs"),
    )
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def user_detail_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    if is_banned:
        kb.add(InlineKeyboardButton("✅ Banı Kaldır", callback_data=f"usr_unban_{user_id}"))
    else:
        kb.add(InlineKeyboardButton("🚫 Banla", callback_data=f"usr_ban_{user_id}"))
    kb.add(InlineKeyboardButton("📣 Mesaj Gönder", callback_data=f"usr_msg_{user_id}"))
    kb.add(InlineKeyboardButton("🎁 Ödülü Manuel Ver", callback_data=f"usr_givereward_{user_id}"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="usr_search"))
    return kb


def broadcast_target_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👥 Herkese Gönder", callback_data="bc_all"))
    kb.add(InlineKeyboardButton("✅ Sadece Üyelere", callback_data="bc_members"))
    kb.add(InlineKeyboardButton("❌ Üye Olmayanlara", callback_data="bc_nonmembers"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def broadcast_confirm_kb(target: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Gönder", callback_data=f"bc_confirm_{target}"),
        InlineKeyboardButton("❌ İptal", callback_data="adm_broadcast"),
    )
    return kb


def reward_mgmt_kb(links) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for lnk in links:
        status = "✅" if lnk["is_active"] else "❌"
        kb.add(InlineKeyboardButton(
            f"{status} {lnk['label']} — {'Aktif' if lnk['is_active'] else 'Pasif'}",
            callback_data=f"rw_toggle_{lnk['id']}"
        ))
        kb.add(InlineKeyboardButton(f"🗑 {lnk['label']} sil", callback_data=f"rw_del_{lnk['id']}"))
    kb.add(InlineKeyboardButton("➕ Link Ekle", callback_data="rw_add"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def messages_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👋 Karşılama Mesajı", callback_data="msg_welcome"))
    kb.add(InlineKeyboardButton("✅ Kanal Sonrası Mesaj", callback_data="msg_success"))
    kb.add(InlineKeyboardButton("🎉 Ödül Mesajı", callback_data="msg_reward"))
    kb.add(InlineKeyboardButton("⏳ Beklemede Mesajı", callback_data="msg_pending"))
    kb.add(InlineKeyboardButton("🔘 Buton Yazısı", callback_data="msg_btntext"))
    kb.add(InlineKeyboardButton("📤 Davet Paylaşım Metni", callback_data="msg_sharetext"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def admins_kb(admins) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for a in admins:
        kb.add(InlineKeyboardButton(f"🗑 Admin #{a['user_id']} sil", callback_data=f"adm_del_{a['user_id']}"))
    kb.add(InlineKeyboardButton("➕ Admin Ekle", callback_data="adm_add"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb


def settings_kb(maintenance: bool, force_join: bool, bot_active: bool, required_refs: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(
        f"🔧 Bakım Modu: {'AÇIK 🟢' if maintenance else 'KAPALI 🔴'}",
        callback_data="set_maintenance"
    ))
    kb.add(InlineKeyboardButton(
        f"🔒 Zorunlu Üyelik: {'AÇIK 🟢' if force_join else 'KAPALI 🔴'}",
        callback_data="set_forcejoin"
    ))
    kb.add(InlineKeyboardButton(
        f"🤖 Bot: {'AKTİF 🟢' if bot_active else 'PASİF 🔴'}",
        callback_data="set_botactive"
    ))
    kb.add(InlineKeyboardButton(
        f"🔢 Gerekli Referans: {required_refs} kişi",
        callback_data="set_required_refs"
    ))
    kb.add(InlineKeyboardButton("✏️ Bakım Mesajı", callback_data="set_maintenancemsg"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="adm_main"))
    return kb
