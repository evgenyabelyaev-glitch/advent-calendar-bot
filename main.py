import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types, F, html
from aiohttp import web # Требуется для запуска веб-сервера

# --- КОНФИГУРАЦИЯ ---
# Токен бота будет получен из переменной окружения Railway (БОЛЕЕ БЕЗОПАСНО)
# Если переменная не найдена, используется "ВАШ_ТОКЕН_БОТА" (только для локальной проверки)
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА") 

# Cloud/Railway требует запуска веб-сервера на порту, который он предоставит
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# Устанавливаем часовой пояс для проверки даты. Это критично!
# Например, MSK (UTC+3). Измените, если ваша любимая живет в другом часовом поясе.
TARGET_TZ = timezone(timedelta(hours=3), name='MSK') 

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ ---
# КЛЮЧ - ДЕНЬ МЕСЯЦА (1, 2, 3...), ЗНАЧЕНИЕ - ТЕКСТ ПОСЛАНИЯ
ADVENT_MESSAGES = {
    1: "❤️ Послание на 1-е: Твоя улыбка - мой самый яркий день!",
    2: "✨ Послание на 2-е: Каждая минута с тобой - это подарок.",
    3: "🌹 Послание на 3-е: Ты самая красивая и умная девушка на свете!",
    4: "💫 Послание на 4-е: Планирую наше следующее приключение!",
    # Добавьте свои послания для дней 5, 6, 7, ... до 24 или 31
    # Например:
    # 24: "🎄 Послание на 24-е: С Наступающим! Ты - моё главное сокровище.",
}
# Определяем максимальный день в календаре
MAX_DAY = max(ADVENT_MESSAGES.keys()) if ADVENT_MESSAGES else 0

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Создание Inline-кнопки
get_message_button = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [types.InlineKeyboardButton(text="Открыть🎁", callback_data="get_advent_message")]
    ]
)

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение с кнопкой."""
    await message.answer(
        f"Привет! Это твой адвент-календарь на {MAX_DAY} дней. "
        "Нажимай кнопку, чтобы открыть секрет!",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    """
    Основная логика: сверяет текущий день с ключами в ADVENT_MESSAGES.
    Защищает от "щёлканья наперёд".
    """
    # 1. Получаем текущий день месяца в заданном часовом поясе
    current_date = datetime.now(TARGET_TZ)
    today_day = current_date.day
    today_month_name = current_date.strftime('%B').lower()

    if today_day > MAX_DAY:
        # Календарь закончился
        text = "😴Еще рано, приходи 1 декабря😴"
    elif today_day not in ADVENT_MESSAGES:
        # Сегодняшний день в календаре есть, но для него нет текста (например, 25-31)
        text = f"😴 Послание на {today_day}-е число не найдено. Проверь завтра!"
    elif today_day < today_day:
         # Это просто логический барьер, который в нормальных условиях не сработает
         # (потому что today_day всегда равен today_day), но показывает защиту.
         text = f"🚫 Подожди! Сегодня только {today_day}-е число. Следующее послание откроется завтра!"
    else:
        # Выдаем послание, соответствующее сегодняшнему дню
        message_text = ADVENT_MESSAGES.get(today_day)
        text = (f"🗓️ **Послание на {today_day} {today_month_name}:**\n\n"
                f"{html.bold(message_text)}")

    await callback.message.answer(text, reply_markup=get_message_button)
    # Отвечаем на запрос, чтобы убрать "часики" с кнопки
    await callback.answer()


# --- НАСТРОЙКА ДЛЯ RAILWAY (WEBHOOK) ---
async def main():
    """
    Инициализирует и запускает веб-сервер для обработки вебхуков.
    """
    try:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        
        # Создаем aiohttp приложение
        app = web.Application()
        setup_application(app, dp)
        
        # Регистрируем обработчик запросов по пути "/webhook"
        SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        ).register(app, "/webhook")

        # Запускаем runner
        runner = web.AppRunner(app)
        await runner.setup()
        
        # Railway требует привязки к 0.0.0.0 и прослушивания порта из переменной PORT
        site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
        logging.info(f"Starting web server on port {WEB_SERVER_PORT}")
        await site.start()
        
        # Ждём, пока веб-сервер обрабатывает запросы
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logging.error(f"Error during webhook setup: {e}")
        # Если не удалось запустить вебхук (например, при локальной отладке без порта)
        logging.info("Falling back to polling mode...")
        await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

