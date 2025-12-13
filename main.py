import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import locale # Модуль для работы с языковыми настройками

from aiogram import Bot, Dispatcher, types, F, html
from aiohttp import web # Требуется для запуска веб-сервера

# --- НАСТРОЙКА РУССКОЙ ЛОКАЛИ ---
# Пытаемся установить русскую локаль для корректного отображения названия месяца (например, "декабря" вместо "December")
try:
    # Попробуем стандартные UNIX/Linux локали
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    try:
        # Попробуем альтернативную форму, которая может работать на некоторых системах
        locale.setlocale(locale.LC_TIME, 'Russian')
    except locale.Error:
        logging.warning("Русская локаль не установлена. Названия месяцев могут быть на английском.")
# ---------------------------------

# --- КОНФИГУРАЦИЯ ---
# Токен бота будет получен из переменной окружения Railway (БОЛЕЕ БЕЗОПАСНО)
# Если переменная не найдена, используется "ВАШ_ТОКЕН_БОТА" (только для локальной проверки)
# Исправлено: Установлен предоставленный токен бота.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8317813238:AAEZly_kyYMZK961uJ32FVYR6xiB31XPylA") 

# Cloud/Railway требует запуска веб-сервера на порту, который он предоставит
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# Устанавливаем часовой пояс для проверки даты. Это критично!
# Например, MSK (UTC+3). Измените, если ваша любимая живет в другом часовом поясе.
TARGET_TZ = timezone(timedelta(hours=3), name='MSK') 

# !!! ВАЖНО: ЗАМЕНИТЕ ЭТО НА ВАШ РЕАЛЬНЫЙ ТЕЛЕГРАМ ID (ЧИСЛО!) !!!
# Сюда будут пересылаться сообщения от пользователя.
# Исправлено: Установлен ID, предоставленный пользователем.
ADMIN_ID = os.getenv("ADMIN_ID", "1126029973")

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ ---
# КЛЮЧ - ДЕНЬ МЕСЯЦА (1, 2, 3...), ЗНАЧЕНИЕ - ТЕКСТ ПОСЛАНИЯ
ADVENT_MESSAGES = {
    1: "🗓 Начало чуда! Сегодняшняя миссия: найди 5 вещей, которые напоминают тебе о Новом годе, и пришли мне их фото. ✨",
    2: "🎁 Твой главный подарок: знать, что моя любовь к тебе безусловна и неизменна. И я это докажу. ❤️",
    3: "🎵 Мини-задание: Включи свою самую любимую песню, которая напоминает тебе зиму и Новый год. И пришли мне ее название. Создаем плейлист нашего праздника! 🎶",
    4: "💭 Сегодня подумай, что тебе хочется в этом декабре больше всего. Ничего глобального. Простое, маленькое желание. Поделись им со мной! 😉",
    5: "✨ Мечты создают реальность! Сегодняшний день принесет тебе маленький шаг к исполнению. Загляни в свой почтовый ящик - там тебя ждет важное напоминание. 💖",
    6: "☕️ Задание дня: Сделай себе самый уютный зимний напиток (чай, какао, кофе) и выпей его, думая о чём-то очень хорошем. 🍵",
    7: "📔 Задание дня: Посмотри в зеркало и назови 3 свои черты, которые тебе в себе нравятся больше всего. А я назову три свои любимые черты в тебе! Твоя красота внутри и снаружи. ❤️",
    8: "🎨 Задание дня: Нарисуй (даже если плохо!) символ Нового года, который ассоциируется с нами. Это может быть елочка, игрушка или снеговик! 🖼️",
    9: "📸 Сегодня подраок для меня: Сделай и пришли мне фото, на котором ты искренне улыбаешься. Мне будет очень приятно, зарядит меня на предстоящую неделю, а еще немного разрушит какие-то барьеры между нами😊",
    10: "💡 Мой главный урок: Ты - моя главная ценность. Моя открытость теперь всегда будет твоей безопасностью. И знай, что ты нужна мне, такой, какая есть❤️",
    11: "📝 Задание дня: Напиши 5 вещей, которые я делаю и они вызывают у тебя самое сильное чувство комфорта и тепла. Это поможет нам стать еще ближе✍️",
    12: "❤️Послание дня: То, что тебе сейчас плохо и беспокойно это временно. А то, что ты сильная, добрая, умная и классная это с тобой навсегда😉 Всплыло одно видео про тебя, смотри на свой страх и риск. Позже можем обсудить: https://t.me/musorka6996/2",
    13: "🏞️Наше мини-приключение. Сегодня нас ждет небольшое путешествие: старинные здания и тишина зимнего леса. Наслаждайся каждым моментом, но помни: самое волшебное и теплое, что мы возьмем с собой - это мы сами. ❤️",
    14: "🫂 Мы вместе. Иногда планы идут не так, как хочется. Это не главное. Главное - мы справимся с чем угодно, если вместе захотим этого. Наши лучшие моменты ещё впереди. Желаю тебе по-настоящему легкого и уютного дня. Обнимаю❤️",
    15: "",
    16: "",
    17: "",
    18: "",
    19: "",
    20: "",
    21: "🍝 Вечер сюрпризов: Сегодня я надену фартук, чтобы создать уют для нас двоих! А вечером, после пасты и бокала чего-то вкусного, тебя ждет сюрприз. Готовься к новому опыту🥂",
    22: "✨ Твой день! Сегодня ты звезда! Съемки пройдут великолепно и ты увидишь себя моими глазами. Ты самая красивая💖",
    23: "",
    24: "",
    25: "",
    26: "",
    27: "",
    28: "",
    29: "",
    30: "",
    31: ""
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
    
    # --- ЛОГИРОВАНИЕ: Запуск бота ---
    logging.info(f"USER_EVENT: START | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")
    # ---------------------------------
    
    await message.answer(
        f"Привет! Это твой адвент-календарь на декабрь. "
        "Нажимай кнопку, чтобы открыть секрет!",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    """
    Основная логика: сверяет текущий день и месяц с календарем.
    Использует единый режим парсинга HTML и русскую локаль для даты.
    """
    
    # --- ЛОГИРОВАНИЕ: Нажатие кнопки ---
    logging.info(f"USER_EVENT: BUTTON_PRESS | Callback: {callback.data} | User ID: {callback.from_user.id} | Name: {callback.from_user.full_name}")
    # ---------------------------------
    
    # 1. Получаем текущие дату и месяц в заданном часовом поясе
    current_date = datetime.now(TARGET_TZ)
    today_day = current_date.day
    today_month = current_date.month
    
    # 2. Форматируем дату в нужный русский формат (например, "2 декабря")
    # %d - день, %B - полное название месяца (будет в родительном падеже благодаря locale)
    formatted_date = current_date.strftime('%d %B')

    # --- ГЛАВНАЯ ПРОВЕРКА: ЕСЛИ НЕ ДЕКАБРЬ ---
    if today_month != 12:
        # Если не Декабрь, выдаем сообщение ожидания.
        text = "😴 Еще рано, приходи 1 декабря! 😴"
    
    # --- ЛОГИКА ДЛЯ ДЕКАБРЯ ---
    elif today_day > MAX_DAY:
        # Календарь закончился
        text = "🎉 Весь адвент-календарь уже открыт! Надеюсь, тебе понравилось! 🎉"
    
    elif today_day not in ADVENT_MESSAGES:
        # Сегодняшний день в календаре есть, но для него нет текста
        text = f"😴 Послание на {formatted_date} не найдено. Проверь завтра!"
        
    else:
        # Выдаем послание, соответствующее сегодняшнему дню (только в Декабре)
        message_text = ADVENT_MESSAGES.get(today_day)
        
        # Используем HTML-форматирование для заголовка и основного текста
        # В заголовок подставляем отформатированную русскую дату
        text = (f"🗓 {html.bold(f'Послание на {formatted_date}:')}\n\n"
                f"{html.bold(message_text)}")
        
        # --- ЛОГИРОВАНИЕ: Успешное открытие сообщения ---
        logging.info(f"ADVENT_MESSAGE_SENT: Day {today_day} sent to User ID: {callback.from_user.id}")
        # ------------------------------------------------

    # Явно указываем parse_mode='HTML'
    await callback.message.answer(text, reply_markup=get_message_button, parse_mode='HTML')
    # Отвечаем на запрос, чтобы убрать "часики" с кнопки
    await callback.answer()


@dp.message()
async def forward_all_messages(message: types.Message):
    """
    Обрабатывает любые сообщения (текст, фото, стикеры и т.д.), 
    которые не были перехвачены другими обработчиками, и пересылает 
    их администратору.
    """
    
    # --- ЛОГИРОВАНИЕ: Получение произвольного сообщения ---
    log_text = message.text[:50] if message.text else f"Non-text message: {message.content_type}"
    logging.info(f"USER_EVENT: ARBITRARY_MESSAGE | Content: '{log_text}' | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")
    # ------------------------------------------------------
    
    try:
        # Проверяем, что ADMIN_ID установлен и не является заглушкой
        if ADMIN_ID and ADMIN_ID != "ВАШ_ADMIN_ID":
            
            # Сообщение, которое будет отправлено администратору
            caption = html.bold("НОВОЕ СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ:\n")
            caption += f"ID пользователя: {html.code(message.chat.id)}\n"
            caption += f"Имя: {html.bold(message.from_user.full_name)}"
            
            # Отправляем администратору информацию о том, от кого сообщение
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=caption, 
                parse_mode='HTML'
            )
            
            # Пересылаем само сообщение администратору
            await bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            
            # Опционально: можно уведомить пользователя, что сообщение принято
            # await message.answer("Спасибо! Ваше сообщение передано.")
            
        else:
            # Если ADMIN_ID не настроен, просто логируем, чтобы не терять сообщения
            logging.warning(f"Сообщение получено от {message.from_user.full_name} ({message.chat.id}), но ADMIN_ID не настроен для пересылки.")
            
    except Exception as e:
        logging.error(f"Ошибка при пересылке сообщения: {e}")
        # Если пересылка не удалась (например, бот не может начать чат с админом)
        await message.answer("Произошла ошибка при обработке вашего сообщения.")


# --- НАСТРОЙКА ДЛЯ RENDER (WEBHOOK) ---
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
        
        # Render/Cloud требует привязки к 0.0.0.0 и прослушивания порта из переменной PORT
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









