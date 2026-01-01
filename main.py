import os
import logging
import asyncio
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
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8317813238:AAEZly_kyYMZK961uC32FVYR6xiB31XPylA") 
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
TARGET_TZ = timezone(timedelta(hours=3), name='MSK') 
ADMIN_ID = os.getenv("ADMIN_ID", "1126029973")

# --- НАСТРОЙКА ID ПОЛЬЗОВАТЕЛЕЙ ---
TARGET_RECIPIENTS_IDS = {
    333121087,
    7891228883,
}

try:
    ADMIN_ID_INT = int(ADMIN_ID)
    TARGET_RECIPIENTS_IDS.add(ADMIN_ID_INT)
except ValueError:
    logging.error("ADMIN_ID не является целым числом.")

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ ---
# Сообщения разделены на два месяца: 12 (Декабрь) и 1 (Январь)
ADVENT_MESSAGES = {
    12: {
        22: "❄️😢 Похолодало! И твои слезки замерзли...",
        23: "🛣️ Легкой дороги! ❤️🚗",
        24: "🏠 С возвращением! ❤️🕯️",
        25: "✨ Сегодня особенный день. Спасибо, что ты есть. ❤️🕯️",
        26: "📝 Вспомни один мой поступок или слово в этом месяце. ❤️",
        27: "🌲 Сегодня у нас важная миссия... подержи меня за руку. ✨🥾❄️",
        28: "☁️ День отдыха! Сжечь кота и посмотреть что-то хорошее! ✨🐱🔥",
        29: "🎄 Вчера было очень круто, спасибо за ёлку и тепло! ❤️✨",
        30: "💌 Месяц почти подошел к концу. Вспомни лучший день декабря? 📆",
        31: "✨ Финал декабря! С наступающим, мой главный подарок! ❤️🥂🎁"
    },
    1: {
        1: "🌟 С Новым Годом! Пусть этот год будет полон любви! (Задание скоро появится)",
        2: "Задание на 2 января",
        3: "Задание на 3 января",
        4: "Задание на 4 января",
        5: "Задание на 5 января",
        6: "Задание на 6 января",
        7: "Задание на 7 января",
        8: "Задание на 8 января",
        9: "Задание на 9 января",
        10: "Задание на 10 января",
        11: "Задание на 11 января",
        12: "Задание на 12 января",
        13: "Задание на 13 января",
        14: "Задание на 14 января",
        15: "Задание на 15 января",
        16: "Задание на 16 января",
        17: "Задание на 17 января",
        18: "Задание на 18 января",
        19: "Задание на 19 января",
        20: "Задание на 20 января",
        21: "Задание на 21 января",
        22: "Задание на 22 января",
        23: "Задание на 23 января",
        24: "Задание на 24 января",
        25: "Задание на 25 января",
        26: "Задание на 26 января",
        27: "Задание на 27 января",
        28: "Задание на 28 января",
        29: "Задание на 29 января",
        30: "Задание на 30 января",
        31: "Задание на 31 января"
    }
} 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

get_message_button = types.InlineKeyboardMarkup(
    inline_keyboard=[[types.InlineKeyboardButton(text="Открыть 🎁", callback_data="get_advent_message")]]
)

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Календарь продолжается! Нажимай кнопку, чтобы открыть секрет дня ✨",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    try:
        if str(callback.from_user.id) != ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"🔔 Кнопку нажала: {callback.from_user.full_name} (ID: {callback.from_user.id})")
    except: pass

    current_date = datetime.now(TARGET_TZ)
    today_day = current_date.day
    today_month = current_date.month
    
    # Проверяем наличие сообщения для текущего месяца и дня
    if today_month in ADVENT_MESSAGES and today_day in ADVENT_MESSAGES[today_month]:
        msg = ADVENT_MESSAGES[today_month][today_day]
        text = f"🗓️ {html.bold(f'Послание на {current_date.strftime('%d %B')}:')}\n\n{msg}"
    else:
        text = "😴 На сегодня заданий пока нет. Загляни завтра!"

    await callback.message.answer(text, reply_markup=get_message_button, parse_mode='HTML')
    await callback.answer()

@dp.message()
async def forward_all_messages(message: types.Message):
    if str(message.from_user.id) == ADMIN_ID: return
    try:
        await bot.send_message(ADMIN_ID, f"📩 От {message.from_user.full_name} ({message.from_user.id}):")
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
        logging.info(f"Server started on port {WEB_SERVER_PORT}")
        await site.start()
        while True: await asyncio.sleep(3600)
    except:
        await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
