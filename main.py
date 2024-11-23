from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import sqlite3
import re
from datetime import datetime, timedelta
from telegram.error import TelegramError

# Вставьте ваш токен и ID каналов
TELEGRAM_TOKEN = '7768498805:AAH9DizsbFe1-P38I-mNyzgZH8aXGACLv-g'
CHANNEL_1_ID = '@ttlltt63'  # Первый канал
CHANNEL_2_ID = '@nijnilove'  # Второй канал
CHANNEL_3_ID = '@NOTlovenino'  # Третий канал

# Глобальный словарь для хранения сообщений пользователей
user_messages = {}

# Регулярное выражение для проверки ссылок
def contains_link(text: str) -> bool:
    """
    Проверяет, содержит ли текст ссылки или упоминания через @.
    """
    url_pattern = r'(?i)\b(?:https?://|www\.)\S+|(?:\b[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+\b)|@[\w\d_]+'
    return bool(re.search(url_pattern, text))

# Функции для работы с базой данных
def init_db():
    """Инициализирует базу данных."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            last_message_time TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def can_send_message(user_id: int) -> bool:
    """Проверяет, может ли пользователь отправить сообщение."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT last_message_time FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        last_message_time = datetime.fromisoformat(result[0])
        return datetime.now() - last_message_time >= timedelta(hours=2)
    return True

def update_last_message_time(user_id: int):
    """Обновляет время последнего сообщения пользователя."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("INSERT OR REPLACE INTO users (user_id, last_message_time) VALUES (?, ?)",
                   (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# Обработчики Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Отправь мне сообщение, и я предложу выбрать канал для пересылки.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    message_text = update.message.text

    if not can_send_message(user_id):
        await update.message.reply_text('Вы можете отправить следующее сообщение только через 2 часа.')
        return

    # Проверка на наличие ссылок
    if message_text and contains_link(message_text):
        await update.message.reply_text('Ваше сообщение содержит ссылку и не будет отправлено.')
        return

    # Сохраняем сообщение пользователя
    user_messages[user_id] = update.message

    # Клавиатура с выбором канала
    keyboard = [
        [InlineKeyboardButton("В Автозаводском любят", callback_data='channel_1')],
        [InlineKeyboardButton("В Нижнем любят", callback_data='channel_2')],
        [InlineKeyboardButton("В Нижнем Не любят", callback_data='channel_3')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Выберите канал, в который хотите отправить сообщение:',
        reply_markup=reply_markup
    )

async def copy_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()  # Закрываем уведомление

    if user_id not in user_messages:
        await query.edit_message_text('Не удалось найти ваше сообщение. Попробуйте снова.')
        return

    message = user_messages.pop(user_id)

    if query.data == 'channel_1':
        target_channel = CHANNEL_1_ID
    elif query.data == 'channel_2':
        target_channel = CHANNEL_2_ID
    elif query.data == 'channel_3':
        target_channel = CHANNEL_3_ID    
    else:
        await query.edit_message_text('Произошла ошибка. Попробуйте снова.')
        return

    try:
        # Копируем сообщение в зависимости от его типа
        if message.text or message.caption:
            await context.bot.copy_message(
                chat_id=target_channel,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
        elif message.photo:
            await context.bot.send_photo(
                chat_id=target_channel,
                photo=message.photo[-1].file_id,
                caption=message.caption if message.caption else ""
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=target_channel,
                video=message.video.file_id,
                caption=message.caption if message.caption else ""
            )

        update_last_message_time(user_id)  # Обновляем время последнего сообщения
        await query.edit_message_text('Ваше сообщение было отправлено!')
    except TelegramError as e:
        await query.edit_message_text(f'Ошибка при отправке сообщения: {e}')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки, возникающие во время обработки сообщений."""
    context.logger.error("Exception while handling an update:", exc_info=context.error)

def main():
    init_db()  # Инициализация базы данных при запуске
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_message))
    app.add_handler(CallbackQueryHandler(copy_to_channel))
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
