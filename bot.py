import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

(OFFER_NAME, OFFER_TYPE, OFFER_COUPON, OFFER_COMMISSION,
 OFFER_FROM, OFFER_DATE, OFFER_COMMENT) = range(7)

(DEAL_NAME, DEAL_VOLUME, DEAL_TYPE, DEAL_DATE,
 DEAL_REPO, DEAL_COMMENT) = range(10, 16)


def cancel_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])

def skip_cancel_btn():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Пропустить", callback_data="skip_comment"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
    ]])

def skip_deal_cancel_btn():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Пропустить", callback_data="skip_deal_comment"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
    ]])

def get_author(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name


# ─── Отмена ───────────────────────────────────────────────────────────────────

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Отменено.")
    else:
        await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


# ─── Меню в групповом чате ────────────────────────────────────────────────────

async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📌 Новое предложение", url=f"https://t.me/{BOT_USERNAME}?start=new_offer"),
        InlineKeyboardButton("🔔 Техника",           url=f"https://t.me/{BOT_USERNAME}?start=new_deal"),
    ]]
    msg = await update.message.reply_text(
        "👇 Выберите действие — диалог откроется в личке с ботом:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await ctx.bot.pin_chat_message(chat_id=update.effective_chat.id, message_id=msg.message_id, disable_notification=True)


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    ctx.user_data["author"] = get_author(update.effective_user)
    if ctx.args:
        if ctx.args[0] == "new_offer":
            await update.message.reply_text("📌 Новое предложение\n\nНазвание бумаги:", reply_markup=cancel_btn())
            return OFFER_NAME
        elif ctx.args[0] == "new_deal":
            await update.message.reply_text("🔔 Техника\n\nНазвание бумаги:", reply_markup=cancel_btn())
            return DEAL_NAME

    keyboard = [[
        InlineKeyboardButton("📌 Новое предложение", callback_data="start_offer"),
        InlineKeyboardButton("🔔 Техника",           callback_data="start_deal"),
    ]]
    await update.message.reply_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    ctx.user_data["author"] = get_author(update.effective_user)
    if query.data == "start_offer":
        await query.edit_message_text("📌 Новое предложение\n\nНазвание бумаги:", reply_markup=cancel_btn())
        return OFFER_NAME
    elif query.data == "start_deal":
        await query.edit_message_text("🔔 Техника\n\nНазвание бумаги:", reply_markup=cancel_btn())
        return DEAL_NAME
    return ConversationHandler.END


# ─── Предложение (вкладка 1) ──────────────────────────────────────────────────

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
    await ctx.bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="Markdown")
    await reply_fn("✅ Готово! Предложение добавлено в таблицу и опубликовано в чате.")
    ctx.user_data.clear()
    return ConversationHandler.END


# ─── Техника (вкладка 2) ──────────────────────────────────────────────────────

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
    await update.message.reply_text("Комментарий (компания Горизонт/ВК и детали, или пропустите):", reply_markup=skip_deal_cancel_btn())
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
    await ctx.bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="Markdown")
    await reply_fn("✅ Готово! Техника добавлена в таблицу и опубликована в чате.")
    ctx.user_data.clear()
    return ConversationHandler.END


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start",     start),
            CommandHandler("new_offer", new_offer),
            CommandHandler("new_deal",  new_deal),
            CallbackQueryHandler(start_callback, pattern="^start_(offer|deal)$"),
        ],
        states={
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
            DEAL_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_name)],
            DEAL_VOLUME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_volume)],
            DEAL_TYPE:    [CallbackQueryHandler(deal_type, pattern="^deal_")],
            DEAL_DATE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_date)],
            DEAL_REPO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, deal_repo)],
            DEAL_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, deal_comment_text),
                CallbackQueryHandler(deal_comment_skip, pattern="^skip_deal_comment$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
        ],
        per_chat=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("menu", menu))

    logger.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
