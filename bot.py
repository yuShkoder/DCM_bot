import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from sheets import SheetsClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ["BOT_TOKEN"]
CHAT_ID      = int(os.environ["CHAT_ID"])
BOT_USERNAME = os.environ["BOT_USERNAME"]

sheets = SheetsClient()

# ── Состояния ConversationHandler ─────────────────────────────────────────────

(OFFER_NAME, OFFER_TYPE, OFFER_COUPON, OFFER_COMMISSION,
 OFFER_FROM, OFFER_DATE, OFFER_COMMENT) = range(7)

(DEAL_NAME, DEAL_VOLUME, DEAL_TYPE, DEAL_DATE,
 DEAL_REPO, DEAL_COMMENT) = range(10, 16)

(EDIT_OFFER_NAME, EDIT_OFFER_TYPE, EDIT_OFFER_COUPON, EDIT_OFFER_COMMISSION,
 EDIT_OFFER_FROM, EDIT_OFFER_DATE, EDIT_OFFER_COMMENT) = range(20, 27)

(EDIT_DEAL_NAME, EDIT_DEAL_VOLUME, EDIT_DEAL_TYPE, EDIT_DEAL_DATE,
 EDIT_DEAL_REPO, EDIT_DEAL_COMMENT) = range(30, 36)

SEARCH_QUERY = 40


# ── Клавиатуры ────────────────────────────────────────────────────────────────

def main_keyboard():
    """Постоянная Reply Keyboard внизу экрана."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📌 Предложение"), KeyboardButton("🔔 Техника")],
            [KeyboardButton("🔍 Поиск"),        KeyboardButton("📊 Статистика")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

def cancel_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])

def skip_cancel_btn():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Пропустить", callback_data="skip_comment"),
        InlineKeyboardButton("❌ Отмена",   callback_data="cancel"),
    ]])

def skip_deal_cancel_btn():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Пропустить", callback_data="skip_deal_comment"),
        InlineKeyboardButton("❌ Отмена",   callback_data="cancel"),
    ]])

def get_author(user) -> str:
    return f"@{user.username}" if user.username else user.full_name


# ── Отмена ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Отменено.")
    else:
        await update.message.reply_text("❌ Отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END


# ── /start и главное меню ─────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    ctx.user_data["author"] = get_author(update.effective_user)

    if ctx.args:
        if ctx.args[0] == "new_offer":
            await update.message.reply_text(
                "📌 Новое предложение\n\nНазвание бумаги:",
                reply_markup=cancel_btn()
            )
            return OFFER_NAME
        elif ctx.args[0] == "new_deal":
            await update.message.reply_text(
                "🔔 Техника\n\nНазвание бумаги:",
                reply_markup=cancel_btn()
            )
            return DEAL_NAME

    await update.message.reply_text(
        "Привет! Выбери действие на клавиатуре внизу 👇",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END


# ── Меню в групповом чате ─────────────────────────────────────────────────────

async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📌 Новое предложение", url=f"https://t.me/{BOT_USERNAME}?start=new_offer"),
        InlineKeyboardButton("🔔 Техника",           url=f"https://t.me/{BOT_USERNAME}?start=new_deal"),
    ]]
    msg = await update.message.reply_text(
        "👇 Выберите действие — диалог откроется в личке с ботом:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await ctx.bot.pin_chat_message(
        chat_id=update.effective_chat.id,
        message_id=msg.message_id,
        disable_notification=True
    )


# ── Обработчик Reply Keyboard ─────────────────────────────────────────────────

async def keyboard_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    ctx.user_data["author"] = get_author(update.effective_user)

    if text == "📌 Предложение":
        ctx.user_data.clear()
        ctx.user_data["author"] = get_author(update.effective_user)
        await update.message.reply_text("📌 Новое предложение\n\nНазвание бумаги:", reply_markup=cancel_btn())
        return OFFER_NAME

    elif text == "🔔 Техника":
        ctx.user_data.clear()
        ctx.user_data["author"] = get_author(update.effective_user)
        await update.message.reply_text("🔔 Техника\n\nНазвание бумаги:", reply_markup=cancel_btn())
        return DEAL_NAME

    elif text == "📊 Статистика":
        await show_stats(update, ctx)

    elif text == "🔍 Поиск":
        await update.message.reply_text("🔍 Введите название бумаги для поиска:", reply_markup=cancel_btn())
        return SEARCH_QUERY

    return ConversationHandler.END


# ── Просмотр: сегодня ─────────────────────────────────────────────────────────

async def show_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today_deals  = sheets.get_today_deals()
    all_offers   = sheets.get_today_offers()

    lines = ["📋 *Записи за сегодня*\n"]

    if all_offers:
        lines.append("📌 *Предложения:*")
        for o in all_offers[-10:]:
            lines.append(
                f"• *{o.get('Название','-')}* | {o.get('Тип','-')} | {o.get('Купон','-')}\n"
                f"  Комиссия: {o.get('Комиссия','-')} | От: {o.get('От кого','-')}\n"
                f"  Размещение: {o.get('Дата размещения','-')}"
            )
    else:
        lines.append("📌 Предложений сегодня нет.")

    lines.append("")

    if today_deals:
        lines.append("🔔 *Техника:*")
        for d in today_deals:
            lines.append(
                f"• *{d.get('Название','-')}* | {d.get('Тип','-')} | {d.get('Объём','-')}\n"
                f"  Дата покупки: {d.get('Дата покупки','-')}\n"
                f"  Репо: {d.get('Репо','-')}"
            )
    else:
        lines.append("🔔 Техники сегодня нет.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard())


# ── Просмотр: статистика ──────────────────────────────────────────────────────

async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = sheets.get_stats()
    text = (
        "📊 *Статистика*\n\n"
        f"📌 *Предложения:* {s['total_offers']} всего\n"
        f"  Флоатеры: {s['floaters']} | Фикс: {s['fixes']}\n\n"
        f"🔔 *Техника:* {s['total_deals']} всего\n"
        f"  Добавлено сегодня: {s['today_deals']}\n"
        f"  Первичка: {s['primary']} | Вторичка: {s['secondary']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())


# ── Поиск ─────────────────────────────────────────────────────────────────────

async def search_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    result = sheets.search_by_name(query)
    offers = result["offers"]
    deals  = result["deals"]
    lines  = [f"🔍 *Результаты по «{query}»*\n"]

    if offers:
        lines.append("📌 *Предложения:*")
        for o in offers:
            lines.append(
                f"• *{o.get('Название','-')}* | {o.get('Тип','-')} | {o.get('Купон','-')}\n"
                f"  Комиссия: {o.get('Комиссия','-')} | От: {o.get('От кого','-')}\n"
                f"  Размещение: {o.get('Дата размещения','-')}"
            )
    else:
        lines.append("📌 Предложений не найдено.")

    lines.append("")

    if deals:
        lines.append("🔔 *Техника:*")
        for d in deals:
            lines.append(
                f"• *{d.get('Название','-')}* | {d.get('Тип','-')} | {d.get('Объём','-')}\n"
                f"  Дата покупки: {d.get('Дата покупки','-')}\n"
                f"  Репо: {d.get('Репо','-')}"
            )
    else:
        lines.append("🔔 Техники не найдено.")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard())
    return ConversationHandler.END


# ── Последняя запись: меню ────────────────────────────────────────────────────

async def show_last_entry_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    last_offer = sheets.get_last_offer()
    last_deal  = sheets.get_last_deal()

    lines = ["✏️ *Последние записи*\n"]

    if last_offer:
        lines.append(
            f"📌 *Предложение:* {last_offer.get('Название','-')} | "
            f"{last_offer.get('Тип','-')} | {last_offer.get('Купон','-')}"
        )
    else:
        lines.append("📌 Предложений нет.")

    if last_deal:
        lines.append(
            f"🔔 *Техника:* {last_deal.get('Название','-')} | "
            f"{last_deal.get('Тип','-')} | {last_deal.get('Объём','-')}"
        )
    else:
        lines.append("🔔 Техники нет.")

    keyboard = []
    if last_offer:
        keyboard.append([
            InlineKeyboardButton("✏️ Изменить предложение", callback_data="edit_offer"),
            InlineKeyboardButton("🗑 Удалить предложение",  callback_data="del_offer"),
        ])
    if last_deal:
        keyboard.append([
            InlineKeyboardButton("✏️ Изменить технику", callback_data="edit_deal"),
            InlineKeyboardButton("🗑 Удалить технику",  callback_data="del_deal"),
        ])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="cancel")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Кнопки редактирования/удаления под постом в группе ───────────────────────

async def group_edit_del_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Кнопки Edit/Delete под сообщением в групповом чате."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "del_last_offer":
        ok = sheets.delete_last_offer()
        await query.edit_message_text(
            query.message.text + ("\n\n✅ Предложение удалено из таблицы." if ok else "\n\n⚠️ Не удалось удалить.")
        )
    elif data == "del_last_deal":
        ok = sheets.delete_last_deal()
        await query.edit_message_text(
            query.message.text + ("\n\n✅ Техника удалена из таблицы." if ok else "\n\n⚠️ Не удалось удалить.")
        )
    elif data in ("edit_last_offer", "edit_last_deal"):
        kind = "offer" if data == "edit_last_offer" else "deal"
        deep = f"edit_{kind}"
        await query.edit_message_text(
            "Нажми кнопку ниже, чтобы открыть редактирование в личке 👇",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✏️ Редактировать в личке",
                    url=f"https://t.me/{BOT_USERNAME}?start={deep}"
                )
            ]])
        )


# ── Удаление из inline-меню (личка) ──────────────────────────────────────────

async def delete_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "del_offer":
        ok = sheets.delete_last_offer()
        await query.edit_message_text("✅ Последнее предложение удалено." if ok else "⚠️ Нечего удалять.")

    elif query.data == "del_deal":
        ok = sheets.delete_last_deal()
        await query.edit_message_text("✅ Последняя техника удалена." if ok else "⚠️ Нечего удалять.")

    elif query.data == "edit_offer":
        last = sheets.get_last_offer()
        if not last:
            await query.edit_message_text("⚠️ Нечего редактировать.")
            return ConversationHandler.END
        ctx.user_data["author"] = get_author(update.effective_user)
        ctx.user_data["editing"] = "offer"
        text = (
            f"✏️ Редактирование предложения\n\n"
            f"Текущее: *{last.get('Название','-')}* | {last.get('Тип','-')} | {last.get('Купон','-')}\n\n"
            f"Новое название бумаги:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_btn())
        return EDIT_OFFER_NAME

    elif query.data == "edit_deal":
        last = sheets.get_last_deal()
        if not last:
            await query.edit_message_text("⚠️ Нечего редактировать.")
            return ConversationHandler.END
        ctx.user_data["author"] = get_author(update.effective_user)
        ctx.user_data["editing"] = "deal"
        text = (
            f"✏️ Редактирование техники\n\n"
            f"Текущее: *{last.get('Название','-')}* | {last.get('Тип','-')} | {last.get('Объём','-')}\n\n"
            f"Новое название бумаги:"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=cancel_btn())
        return EDIT_DEAL_NAME


# ── Редактирование предложения ────────────────────────────────────────────────

async def edit_offer_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    keyboard = [[
        InlineKeyboardButton("Флоатер", callback_data="etype_floater"),
        InlineKeyboardButton("Фикс",    callback_data="etype_fix"),
    ], [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text("Тип бумаги:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_OFFER_TYPE

async def edit_offer_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["type"] = "Флоатер" if query.data == "etype_floater" else "Фикс"
    await query.edit_message_text(f"Тип: {ctx.user_data['type']}\n\nКупон:", reply_markup=cancel_btn())
    return EDIT_OFFER_COUPON

async def edit_offer_coupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["coupon"] = update.message.text.strip()
    await update.message.reply_text("Комиссия:", reply_markup=cancel_btn())
    return EDIT_OFFER_COMMISSION

async def edit_offer_commission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["commission"] = update.message.text.strip()
    await update.message.reply_text("От кого предложение:", reply_markup=cancel_btn())
    return EDIT_OFFER_FROM

async def edit_offer_from(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["from"] = update.message.text.strip()
    await update.message.reply_text("Предполагаемая дата размещения:", reply_markup=cancel_btn())
    return EDIT_OFFER_DATE

async def edit_offer_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("Комментарий (или пропустите):", reply_markup=skip_cancel_btn())
    return EDIT_OFFER_COMMENT

async def edit_offer_comment_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["comment"] = update.message.text.strip()
    return await _save_edit_offer(update.message.reply_text, ctx)

async def edit_offer_comment_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["comment"] = ""
    return await _save_edit_offer(query.edit_message_text, ctx)

async def _save_edit_offer(reply_fn, ctx):
    d = ctx.user_data
    row = [d["name"], d["type"], d["coupon"], d["commission"], d["from"], d["date"], d.get("comment", "")]
    sheets.update_last_offer(row)
    await reply_fn("✅ Предложение обновлено в таблице.", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Редактирование техники ────────────────────────────────────────────────────

async def edit_deal_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Объём:", reply_markup=cancel_btn())
    return EDIT_DEAL_VOLUME

async def edit_deal_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["volume"] = update.message.text.strip()
    keyboard = [[
        InlineKeyboardButton("Первичка", callback_data="edeal_primary"),
        InlineKeyboardButton("Вторичка", callback_data="edeal_secondary"),
    ], [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text("Тип:", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_DEAL_TYPE

async def edit_deal_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["type"] = "Первичка" if query.data == "edeal_primary" else "Вторичка"
    await query.edit_message_text(f"Тип: {ctx.user_data['type']}\n\nДата покупки:", reply_markup=cancel_btn())
    return EDIT_DEAL_DATE

async def edit_deal_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("Репо:", reply_markup=cancel_btn())
    return EDIT_DEAL_REPO

async def edit_deal_repo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["repo"] = update.message.text.strip()
    await update.message.reply_text("Комментарий (или пропустите):", reply_markup=skip_deal_cancel_btn())
    return EDIT_DEAL_COMMENT

async def edit_deal_comment_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["comment"] = update.message.text.strip()
    return await _save_edit_deal(update.message.reply_text, ctx)

async def edit_deal_comment_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["comment"] = ""
    return await _save_edit_deal(query.edit_message_text, ctx)

async def _save_edit_deal(reply_fn, ctx):
    d = ctx.user_data
    from datetime import datetime
    today = datetime.now().strftime("%d.%m.%Y")
    row = [d["name"], d["volume"], d["type"], d["date"], d["repo"], d.get("comment", ""), today]
    sheets.update_last_deal(row)
    await reply_fn("✅ Техника обновлена в таблице.", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Предложение (создание) ────────────────────────────────────────────────────

async def new_offer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != update.effective_user.id:
        keyboard = [[InlineKeyboardButton("📌 Открыть в личке", url=f"https://t.me/{BOT_USERNAME}?start=new_offer")]]
        await update.message.reply_text("Нажми кнопку — диалог откроется в личке 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    ctx.user_data.clear()
    ctx.user_data["author"] = get_author(update.effective_user)
    await update.message.reply_text("📌 Новое предложение\n\nНазвание бумаги:", reply_markup=cancel_btn())
    return OFFER_NAME

async def offer_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    keyboard = [[
        InlineKeyboardButton("Флоатер", callback_data="type_floater"),
        InlineKeyboardButton("Фикс",    callback_data="type_fix"),
    ], [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text("Тип бумаги:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OFFER_TYPE

async def offer_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["type"] = "Флоатер" if query.data == "type_floater" else "Фикс"
    await query.edit_message_text(f"Тип: {ctx.user_data['type']}\n\nКупон (например: КС+150бп или 15,4%):", reply_markup=cancel_btn())
    return OFFER_COUPON

async def offer_coupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["coupon"] = update.message.text.strip()
    await update.message.reply_text("Комиссия (например: 0,25%):", reply_markup=cancel_btn())
    return OFFER_COMMISSION

async def offer_commission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["commission"] = update.message.text.strip()
    await update.message.reply_text("От кого предложение (эмитент / организатор):", reply_markup=cancel_btn())
    return OFFER_FROM

async def offer_from(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["from"] = update.message.text.strip()
    await update.message.reply_text("Предполагаемая дата размещения:", reply_markup=cancel_btn())
    return OFFER_DATE

async def offer_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("Дополнительный комментарий (или пропустите):", reply_markup=skip_cancel_btn())
    return OFFER_COMMENT

async def offer_comment_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["comment"] = update.message.text.strip()
    return await _save_offer(update.message.reply_text, ctx)

async def offer_comment_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["comment"] = ""
    return await _save_offer(query.edit_message_text, ctx)

async def _save_offer(reply_fn, ctx):
    d = ctx.user_data
    sheets.append_offer([d["name"], d["type"], d["coupon"], d["commission"], d["from"], d["date"], d.get("comment", "")])
    lines = [
        "📌 *Новое предложение*",
        f"*{d['name']}* | {d['type']} | {d['coupon']}",
        f"Комиссия: {d['commission']} | От: {d['from']}",
        f"Размещение: {d['date']}",
    ]
    if d.get("comment"):
        lines.append(f"💬 {d['comment']}")
    lines.append(d["author"])

    # Кнопки под постом в группе
    group_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Изменить", callback_data="edit_last_offer"),
        InlineKeyboardButton("🗑 Удалить",  callback_data="del_last_offer"),
    ]])
    await ctx.bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="Markdown", reply_markup=group_kb)
    await reply_fn("✅ Готово! Предложение добавлено в таблицу и опубликовано в чате.", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Техника (создание) ────────────────────────────────────────────────────────

async def new_deal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != update.effective_user.id:
        keyboard = [[InlineKeyboardButton("🔔 Открыть в личке", url=f"https://t.me/{BOT_USERNAME}?start=new_deal")]]
        await update.message.reply_text("Нажми кнопку — диалог откроется в личке 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    ctx.user_data.clear()
    ctx.user_data["author"] = get_author(update.effective_user)
    await update.message.reply_text("🔔 Техника\n\nНазвание бумаги:", reply_markup=cancel_btn())
    return DEAL_NAME

async def deal_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Объём:", reply_markup=cancel_btn())
    return DEAL_VOLUME

async def deal_volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["volume"] = update.message.text.strip()
    keyboard = [[
        InlineKeyboardButton("Первичка", callback_data="deal_primary"),
        InlineKeyboardButton("Вторичка", callback_data="deal_secondary"),
    ], [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]]
    await update.message.reply_text("Тип:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEAL_TYPE

async def deal_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["type"] = "Первичка" if query.data == "deal_primary" else "Вторичка"
    await query.edit_message_text(f"Тип: {ctx.user_data['type']}\n\nДата покупки:", reply_markup=cancel_btn())
    return DEAL_DATE

async def deal_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["date"] = update.message.text.strip()
    await update.message.reply_text("Репо (кто сколько когда уйдёт):", reply_markup=cancel_btn())
    return DEAL_REPO

async def deal_repo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["repo"] = update.message.text.strip()
    await update.message.reply_text("Комментарий (или пропустите):", reply_markup=skip_deal_cancel_btn())
    return DEAL_COMMENT

async def deal_comment_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["comment"] = update.message.text.strip()
    return await _save_deal(update.message.reply_text, ctx)

async def deal_comment_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["comment"] = ""
    return await _save_deal(query.edit_message_text, ctx)

async def _save_deal(reply_fn, ctx):
    d = ctx.user_data
    sheets.append_deal([d["name"], d["volume"], d["type"], d["date"], d["repo"], d.get("comment", "")])
    lines = [
        "🔔 *Техника*",
        f"*{d['name']}* | {d['type']} | {d['volume']}",
        f"Дата покупки: {d['date']}",
        f"Репо: {d['repo']}",
    ]
    if d.get("comment"):
        lines.append(f"💬 {d['comment']}")
    lines.append(d["author"])

    # Кнопки под постом в группе
    group_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Изменить", callback_data="edit_last_deal"),
        InlineKeyboardButton("🗑 Удалить",  callback_data="del_last_deal"),
    ]])
    await ctx.bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="Markdown", reply_markup=group_kb)
    await reply_fn("✅ Готово! Техника добавлена в таблицу и опубликована в чате.", reply_markup=main_keyboard())
    ctx.user_data.clear()
    return ConversationHandler.END


# ── Запуск ────────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",     start),
            CommandHandler("new_offer", new_offer),
            CommandHandler("new_deal",  new_deal),
            # Reply Keyboard — точки входа через текстовые кнопки
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(
                    "^(📌 Предложение|🔔 Техника|🔍 Поиск|📊 Статистика)$"
                ),
                keyboard_handler
            ),
        ],
        states={
            # Создание предложения
            OFFER_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_name)],
            OFFER_TYPE:       [CallbackQueryHandler(offer_type, pattern="^type_")],
            OFFER_COUPON:     [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_coupon)],
            OFFER_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_commission)],
            OFFER_FROM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_from)],
            OFFER_DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_date)],
            OFFER_COMMENT:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, offer_comment_text),
                CallbackQueryHandler(offer_comment_skip, pattern="^skip_comment$"),
            ],
            # Создание техники
            DEAL_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_name)],
            DEAL_VOLUME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_volume)],
            DEAL_TYPE:    [CallbackQueryHandler(deal_type, pattern="^deal_")],
            DEAL_DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_date)],
            DEAL_REPO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_repo)],
            DEAL_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, deal_comment_text),
                CallbackQueryHandler(deal_comment_skip, pattern="^skip_deal_comment$"),
            ],
            # Редактирование предложения
            EDIT_OFFER_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_name)],
            EDIT_OFFER_TYPE:       [CallbackQueryHandler(edit_offer_type, pattern="^etype_")],
            EDIT_OFFER_COUPON:     [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_coupon)],
            EDIT_OFFER_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_commission)],
            EDIT_OFFER_FROM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_from)],
            EDIT_OFFER_DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_date)],
            EDIT_OFFER_COMMENT:    [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_offer_comment_text),
                CallbackQueryHandler(edit_offer_comment_skip, pattern="^skip_comment$"),
            ],
            # Редактирование техники
            EDIT_DEAL_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_deal_name)],
            EDIT_DEAL_VOLUME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_deal_volume)],
            EDIT_DEAL_TYPE:    [CallbackQueryHandler(edit_deal_type, pattern="^edeal_")],
            EDIT_DEAL_DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_deal_date)],
            EDIT_DEAL_REPO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_deal_repo)],
            EDIT_DEAL_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_deal_comment_text),
                CallbackQueryHandler(edit_deal_comment_skip, pattern="^skip_deal_comment$"),
            ],
            # Поиск
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        per_chat=False,
    )

    # Обработчики inline-кнопок (вне conversation)
    app.add_handler(CallbackQueryHandler(
        delete_callback,
        pattern="^(del_offer|del_deal|edit_offer|edit_deal)$"
    ))
    app.add_handler(CallbackQueryHandler(
        group_edit_del_callback,
        pattern="^(del_last_offer|del_last_deal|edit_last_offer|edit_last_deal)$"
    ))

    # Обработчики кнопок Reply Keyboard, не входящих в conversation
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex("^📊 Статистика$"),
        keyboard_handler
    ))

    app.add_handler(conv)
    app.add_handler(CommandHandler("menu", menu))

    logger.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
