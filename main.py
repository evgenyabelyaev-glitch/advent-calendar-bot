import os
import logging
import asyncio
import json
from datetime import datetime, timezone, timedelta
import locale

# --- НАСТРОЙКА РУССКОЙ ЛОКАЛИ ---
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Russian')
    except locale.Error:
        logging.warning("Русская локаль не установлена.")

from aiogram import Bot, Dispatcher, types, F, html
from aiogram.filters import Command
from aiohttp import web

# --- ИМПОРТЫ FIREBASE ---
import firebase_admin
from firebase_admin import credentials, firestore

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8317813238:AAEZly_kyYMZK961uC32FVYR6xiB31XPylA") 
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
TARGET_TZ = timezone(timedelta(hours=3), name='MSK') 
ADMIN_ID = os.getenv("ADMIN_ID", "1126029973")
APP_ID = os.getenv("__app_id", "default-app-id")

# --- ИНИЦИАЛИЗАЦИЯ FIREBASE ---
firebase_cfg_raw = os.getenv("__firebase_config")
if firebase_cfg_raw:
    try:
        firebase_cfg = json.loads(firebase_cfg_raw)
        cred = credentials.Certificate(firebase_cfg)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        logging.error(f"Firebase init error: {e}")
        db = None
else:
    db = None

USERS_COLLECTION = f"artifacts/{APP_ID}/public/data/users"

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ (МАРТ) ---
# Замените текст в кавычках на ваши авторские послания
ADVENT_MESSAGES = {
    3: {
        2: "🌸 Начинаем подготовку к празднику! И сегодня у нас мини-викторина: \n1. Чем пахла кошка, когда ее только взяли? \n2. Какое самое первое колечко я тебе подарил? \n3. Какой у тебя был телефон, когда мы познакомились? \nА чтобы лучше думалось, немного приятных слов: я очень горжусь, что у меня такая женщина - у тебя много увлечений, ты добрая и заботливая, даже в такой сложный для нас период. Я тебя люблю",
        3: "✨ [ВАШ ТЕКСТ ДНЯ: 3 МАРТА]",
        4: "🌿 [ВАШ ТЕКСТ ДНЯ: 4 МАРТА]",
        5: "🍬 [ВАШ ТЕКСТ ДНЯ: 5 МАРТА]",
        6: "🎈 [ВАШ ТЕКСТ ДНЯ: 6 МАРТА]",
        7: "🌙 [ВАШ ТЕКСТ ДНЯ: 7 МАРТА]",
        8: "💐 [ГЛАВНОЕ ПОСЛАНИЕ: 8 МАРТА]"
    }
} 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кнопка теперь с весенним эмодзи
get_message_button = types.InlineKeyboardMarkup(
    inline_keyboard=[[types.InlineKeyboardButton(text="Открыть послание 🌸", callback_data="get_advent_message")]]
)

async def save_user(user: types.User):
    if db:
        try:
            user_ref = db.collection(USERS_COLLECTION).document(str(user.id))
            user_ref.set({
                "id": user.id,
                "full_name": user.full_name,
                "username": user.username,
                "last_seen": datetime.now(timezone.utc)
            }, merge=True)
        except Exception as e:
            logging.error(f"Error saving user: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await save_user(message.from_user)
    await message.answer(
        "Привет! Твой весенний календарь-сюрприз готов. Каждый день до 8 марта здесь будет появляться что-то особенное. ✨",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    current_date = datetime.now(TARGET_TZ)
    today_day = current_date.day
    today_month = current_date.month
    
    # Уведомление админу
    if str(callback.from_user.id) != ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f"🔔 Соня открыла календарь за {today_day} марта!")
        except: pass

    if today_month == 3 and today_day in ADVENT_MESSAGES[3]:
        msg = ADVENT_MESSAGES[3][today_day]
        date_str = current_date.strftime('%d %B')
        text = f"🗓️ {html.bold(f'Послание на {date_str}:')}\n\n{msg}"
    elif today_month == 3 and today_day < 2:
        text = "⏳ Твой весенний календарь начнется 2 марта. Совсем скоро! 🌱"
    else:
        text = "😴 На сегодня всё. Новое весеннее послание появится завтра утром!"

    await callback.message.answer(text, reply_markup=get_message_button, parse_mode='HTML')
    await callback.answer()

@dp.message()
async def forward_all_messages(message: types.Message):
    if str(message.from_user.id) == ADMIN_ID: return
    try:
        await bot.send_message(ADMIN_ID, f"📩 Сообщение от неё:")
        await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    except: pass

async def main():
    try:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        app = web.Application()
        setup_application(app, dp)
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, "/webhook")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
        await site.start()
        while True: await asyncio.sleep(3600)
    except:
        await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


