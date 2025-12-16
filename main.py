import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import locale # Модуль для работы с языковыми настройками

from aiogram import Bot, Dispatcher, types, F, html
from aiohttp import web # Требуется для запуска веб-сервера

# --- ИМПОРТЫ ДЛЯ FIREBASE ---
import firebase_admin
from firebase_admin import credentials, firestore
import json
# ----------------------------

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

# Переменные, предоставленные Canvas для Firebase
APP_ID = os.environ.get('__app_id', 'default-app-id')
FIREBASE_CONFIG_JSON = os.environ.get('__firebase_config')

# --- ИДЕНТИФИКАТОРЫ ПОЛЬЗОВАТЕЛЕЙ (Теперь только для инициализации) ---
USER_IDS = set() 

# --- НАСТРОЙКА FIREBASE ---
db = None # Ссылка на Firestore
def init_firebase():
    """Инициализация Firebase с использованием конфигурации Canvas."""
    global db
    if FIREBASE_CONFIG_JSON and not firebase_admin._apps:
        try:
            firebase_config = json.loads(FIREBASE_CONFIG_JSON)
            
            # Используем предоставленную структуру конфигурации для опций инициализации
            options = {'projectId': firebase_config.get('projectId')}
            
            # Пытаемся инициализировать без явных учетных данных, полагаясь на окружение
            firebase_admin.initialize_app(options=options)
            
            db = firestore.client()
            logging.info("Firebase initialized successfully. Firestore client ready.")
            return True
        except Exception as e:
            # Улучшенное логирование фатальной ошибки
            logging.error(f"FATAL ERROR: Failed to initialize Firebase Admin SDK. Persistence will not work. Error: {e}")
            db = None # Убеждаемся, что db равно None при ошибке
            return False
    elif not firebase_admin._apps:
         logging.warning("FIREBASE_CONFIG environment variable not found. Data persistence is disabled.")
         db = None
         return False
    return True

# --- ФУНКЦИИ FIREBASE ДЛЯ ХРАНЕНИЯ ID ---

def get_user_doc_ref(user_id):
    """Возвращает ссылку на документ пользователя в Firestore."""
    # Публичная коллекция: /artifacts/{appId}/public/data/users/{userId}
    return db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('users').document(str(user_id))

async def save_user_id(user_id, username, full_name):
    """Сохраняет ID пользователя в Firestore."""
    if not db:
        logging.error(f"Cannot save user {user_id}. Firestore client is not initialized.")
        return
        
    doc_ref = get_user_doc_ref(user_id)
    
    # Используем `set` с merge=True, чтобы обновить, но не перезаписать другие поля
    user_data = {
        'id': user_id,
        'username': username,
        'full_name': full_name,
        'last_interaction': datetime.now(timezone.utc)
    }
    
    try:
        # NOTE: Эта синхронная функция оборачивается в asyncio.to_thread
        await asyncio.to_thread(doc_ref.set, user_data, merge=True)
        logging.info(f"User ID {user_id} saved/updated in Firestore.")
    except Exception as e:
        # Добавлено агрессивное логирование ошибок
        logging.error(f"CRITICAL ERROR SAVING TO FIREBASE! User ID: {user_id}. Error details: {e}")

async def get_all_user_ids_from_db():
    """Загружает все ID пользователей из Firestore для рассылки."""
    if not db:
        return set()
        
    try:
        # Получаем коллекцию пользователей: /artifacts/{appId}/public/data/users
        collection_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('users')
        
        # Получаем все документы в коллекции
        users_stream = await asyncio.to_thread(collection_ref.stream)
        
        user_ids = {doc.id for doc in users_stream}
        logging.info(f"Loaded {len(user_ids)} user IDs from Firestore.")
        return user_ids
    except Exception as e:
        logging.error(f"Error loading user IDs from Firestore: {e}")
        return set()

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ ---
# КЛЮЧ - ДЕНЬ МЕСЯЦА (1, 2, 3...), ЗНАЧЕНИЕ - ТЕКСТ ПОСЛАНИЯ
ADVENT_MESSAGES = {
    # === НЕДЕЛЯ 1: СВЕТ И ЛЕГКОСТЬ ===
    1: "🗓️ Начало чуда! Сегодняшняя миссия: найди 5 вещей, которые напоминают тебе о Новом годе, и пришли мне их фото. ✨",
    2: "🎁 Твой главный подарок: знать, что моя любовь к тебе безусловна и неизменна. И я это докажу. ❤️",
    3: "🎵 Мини-задание: Включи свою самую любимую, но очень старую новогоднюю песню. И пришли мне ее название. Создаем плейлист нашего праздника! 🎶",
    4: "💫 Ты — мой личный 'Северный свет'. Ты сияешь даже в самые пасмурные дни. Спасибо за то, что ты есть. 💖",
    5: "💌 Помни о самой важной магии зимы: **\"Мечтай — и сбудется\"**. Чтобы ты никогда не забывала это простое правило, я оставил тебе кое-что. Проверь почтовый ящик, это личный талисман. 🍀", # Обновлено на вариант с браслетом
    6: "🪞 Задание дня: Посмотри в зеркало и назови 3 свои черты, которые тебе в себе нравятся больше всего. А я назову три свои любимые черты в тебе! Твоя красота внутри и снаружи. ❤️", # Новый вариант
    7: "🎬 Мини-отдых! Сегодня вечером наша миссия — полное расслабление. Напиши мне, какой самый уютный фильм ты хотела бы посмотреть. Я готовлю попкорн! 🍿", # Новый вариант
    # === НЕДЕЛЯ 2: ТЕПЛО И БЛИЗОСТЬ / СОВМЕСТНОЕ ТВОРЧЕСТВО ===
    8: "👃 Закрой глаза. Подумай, какой запах для тебя самый новогодний (мандарины, ель, корица)? Пришли мне его название. Я буду представлять, что мы его чувствуем вместе. ✨", 
    9: "📸 **Время для меня:** Сделай 'селфи счастья'. Пришли мне фото, на котором ты искренне улыбаешься. Это мой личный заряд энергии! 😊", # Адаптировано
    10: "💡 **Мой главный урок:** Ты — моя главная ценность. Я обещаю: моя открытость всегда будет твоей безопасностью. Просто знай, что ты нужна мне, такой, какая есть. 💯", # Адаптировано
    11: "📝 **Задание дня:** Напиши 5 вещей, которые я делаю, и которые вызывают у тебя самое сильное чувство комфорта и тепла. Это поможет мне узнать тебя лучше сейчас. ✍️", # Адаптировано
    12: "🍝 **Вечер сюрпризов:** Сегодня я надену фартук, чтобы создать уют для нас двоих! А вечером, после пасты и бокала чего-то вкусного, тебя ждет кое-что важное. Готовься к новому приключению! 🥂", # Адаптировано под планы
    13: "✨ **Твой день!** Сегодня ты — абсолютная звезда. Иди и сияй! Съемки пройдут великолепно, и ты увидишь себя моими глазами. Ты самая красивая! 💖", # Адаптировано под фотосессию
    14: "🫂 **Мы вместе.** Иногда планы идут не так, как хочется. Но знаешь что? Это не главное. Главное — мы справимся с чем угодно. Я здесь, чтобы поддержать тебя. Наши лучшие моменты ещё впереди. Обнимаю. ❤️", # Обновлено после неудачной фотосессии
    # === НЕДЕЛЯ 3: ВОЛШЕБСТВО И УДИВЛЕНИЕ ===
    15: "🏞️ **Наше мини-приключение.** Сегодня нас ждет небольшое путешествие: старинные здания и тишина зимнего леса. Наслаждайся каждым моментом, но помни: самое волшебное и теплое, что мы возьмем с собой — это мы сами. ❤️", # Адаптировано под поездку (монастырь, лес)
    16: "🎁Сегодня задание с наградой! Собери пазл на любой сложности (https://grandgames.net/puzzle/online/u_yolki__1), пришли мне итоговую картинку и ссылку на маркетплейс на штучку, которая сделала бы наш отпускной вечер в доме уютнее и сделала бы нас ближе💕", # Новое сообщение: Фокус на силе и достижениях
    17: "",
    18: "☀️ Послание на 18-е: Даже в самый пасмурный день ты - моё солнце.",
    19: "🍿 Послание на 17-е: Предлагаю сегодня вечером просмотр фильма и никакого беспокойства :)",
    20: "🕰️ Послание на 20-е: Время, проведенное с тобой самое лучшее!",
    21: "🌳 Послание на 21-е: ",
    # === НЕДЕЛЯ 4: ФИНАЛ И ПРАЗДНИК ===
    22: "🎁 Послание на 22-е: Сюрприз! Зайди в... (место, где вы спрятали маленький подарок).",
    23: "📸 Послание на 23-е: Отправь мне своё лучшее селфи дня. Оно гарантированно поднимет мне настроение.",
    24: "🥂 Послание на 24-е: Сегодня — идеальный повод, чтобы отпраздновать наш маленький праздник.",
    25: "🔥 Послание на 25-е: Ты делаешь мою жизнь горячее, чем самый острый перец.",
    26: "🎤 Послание на 26-е: Спой для меня что-нибудь. Я буду слушать, затаив дыхание.",
    27: "🧩 Послание на 27-е: Мы отлично прошли этот месяц. Спасибо за каждый день рядом!",
    28: "🔮 Послание на 28-е: Мои предсказания: нас ждет волшебное будущее!",
    29: "🗺️ Послание на 29-е: Куда бы ни привела нас жизнь, я всегда буду рядом.",
    30: "💌 Послание на 30-е: Это почти финал! Знай, ты — самое лучшее, что со мной случилось.",
    31: "🥳 Послание на 31-е: Поздравляю! Мы это сделали! Отпразднуем? Ты — мой главный подарок в жизни."
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

@dp.message(F.text.startswith("/force_save_user"), F.from_user.id == int(ADMIN_ID))
async def cmd_force_save_user(message: types.Message):
    """Позволяет администратору принудительно добавить ID пользователя в базу данных."""
    
    # Извлекаем аргументы: /force_save_user <ID> <Full Name...>
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        return await message.answer(
            "❌ Неверный формат. Используйте: /force_save_user <ID пользователя> <Полное имя>"
        )
        
    user_id_str = parts[1].strip()
    full_name = parts[2].strip()
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        return await message.answer("❌ ID пользователя должен быть числом.")

    if not db:
        return await message.answer("❌ Ошибка: База данных Firebase не инициализирована. Сохранение невозможно.")

    # Принудительное сохранение
    await save_user_id(
        user_id=user_id,
        username=None, # Username неизвестен при принудительном добавлении
        full_name=full_name
    )

    # Проверка сохранения (опционально, но полезно)
    target_user_ids = await get_all_user_ids_from_db()
    if str(user_id) in target_user_ids:
        await message.answer(
            f"✅ Пользователь **{full_name}** (ID: `{user_id}`) **успешно добавлен** в базу данных Firestore.\n"
            "Теперь он должен получать рассылки.",
            parse_mode='Markdown'
        )
    else:
        await message.answer(
            f"⚠️ Пользователь **{full_name}** (ID: `{user_id}`) был обработан, но **не найден** при повторной проверке базы. Возможно, возникла ошибка доступа к Firestore. Проверьте логи.",
            parse_mode='Markdown'
        )

@dp.message(F.text == "/check_users", F.from_user.id == int(ADMIN_ID))
async def cmd_check_users(message: types.Message):
    """Проверяет количество сохраненных пользователей в Firestore."""
    logging.info(f"ADMIN_EVENT: /check_users initiated by {message.from_user.id}")
    
    if not db:
        await message.answer("❌ Ошибка: База данных Firebase не инициализирована. Проверьте логи на ошибки при запуске.")
        return

    try:
        target_user_ids = await get_all_user_ids_from_db()
        count = len(target_user_ids)
        
        if count == 0:
            report_text = "⚠️ В базе данных **нет сохраненных пользователей** (помимо администратора)."
        else:
            report_text = f"✅ В базе данных обнаружено **{count}** сохраненных пользователей."
            # Добавим список ID для отладки
            id_list = "\n".join(f"- `{id}`" for id in sorted(list(target_user_ids)))
            
            # Показываем только первые 10 ID, если их много
            if len(target_user_ids) > 10:
                report_text += "\n\n(Показаны только первые 10 ID)"
                id_list = "\n".join(f"- `{id}`" for id in sorted(list(target_user_ids))[:10])
                
            report_text += f"\n\n**Список ID:**\n{id_list}"

        await message.answer(report_text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error during /check_users command: {e}")
        await message.answer(f"❌ Произошла ошибка при получении данных из базы: {e}")


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение с кнопкой и сохраняет ID пользователя."""
    
    # --- ЛОГИРОВАНИЕ: Запуск бота ---
    logging.info(f"USER_EVENT: START | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")
    # ---------------------------------
    
    # Сохраняем ID пользователя в Firestore (если он не администратор)
    if str(message.from_user.id) != ADMIN_ID:
        await save_user_id(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )

    await message.answer(
        f"Привет! Это твой адвент-календарь на декабрь. "
        "Нажимай кнопку, чтобы открыть секрет!",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    """
    Основная логика: сверяет текущий день и месяц с календарем, сохраняет ID пользователя 
    и отправляет уведомление администратору о нажатии кнопки.
    """
    
    # --- ЛОГИРОВАНИЕ: Нажатие кнопки ---
    logging.info(f"USER_EVENT: BUTTON_PRESS | Callback: {callback.data} | User ID: {callback.from_user.id} | Name: {callback.from_user.full_name}")
    # ---------------------------------
    
    # Сохраняем ID пользователя в Firestore (если он не администратор)
    if str(callback.from_user.id) != ADMIN_ID:
        await save_user_id(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name
        )
    
    # --- УВЕДОМЛЕНИЕ АДМИНИСТРАТОРУ О НАЖАТИИ КНОПКИ ---
    notification_text = (
        f"🔔 {html.bold('КНОПКА АДВЕНТ-КАЛЕНДАРЯ НАЖАТА!')}\n"
        f"Пользователь: {html.bold(callback.from_user.full_name)}\n"
        f"ID: {html.code(callback.from_user.id)}\n"
        f"Время: {datetime.now(TARGET_TZ).strftime('%H:%M:%S')}"
    )
    
    try:
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=notification_text, 
            parse_mode='HTML'
        )
        logging.info(f"ADMIN_NOTIFICATION: Button press notification sent for User ID: {callback.from_user.id}")
    except Exception as e:
        logging.error(f"Error sending button notification to ADMIN_ID {ADMIN_ID}: {e}")
    # --------------------------------------------------

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
        text = (f"🗓️ {html.bold(f'Послание на {formatted_date}:')}\n\n"
                f"{html.bold(message_text)}")
        
        # --- ЛОГИРОВАНИЕ: Успешное открытие сообщения ---
        logging.info(f"ADVENT_MESSAGE_SENT: Day {today_day} sent to User ID: {callback.from_user.id}")
        # ------------------------------------------------

    # Явно указываем parse_mode='HTML'
    await callback.message.answer(text, reply_markup=get_message_button, parse_mode='HTML')
    # Отвечаем на запрос, чтобы убрать "часики" с кнопки
    await callback.answer()


@dp.message(F.text.startswith("/broadcast"), F.from_user.id == int(ADMIN_ID))
async def cmd_broadcast(message: types.Message):
    """
    Позволяет администратору отправить произвольное сообщение ВСЕМ пользователям.
    Формат: /broadcast <текст сообщения>
    """
    
    # 1. Извлекаем текст сообщения, удаляя команду
    text_to_send = message.text.replace("/broadcast", "", 1).strip()

    if not text_to_send:
        return await message.answer("Пожалуйста, укажите текст для рассылки. Формат: /broadcast <текст>")

    # 2. Загружаем актуальный список пользователей из Firestore
    target_user_ids = await get_all_user_ids_from_db()
    
    if not target_user_ids:
        # Улучшенный ответ, чтобы предложить отладку
        return await message.answer("❌ Ошибка: Нет сохраненных пользователей для рассылки в базе данных. Попробуйте команду /check_users для отладки.")
    
    success_count = 0
    fail_count = 0
    
    # 3. Итерация по всем сохраненным ID
    for user_id in target_user_ids: # Используем SET из базы
        try:
            # 4. Отправляем сообщение пользователю
            await bot.send_message(
                chat_id=int(user_id), # ID из Firestore - строка, преобразуем в число
                text=text_to_send,
                parse_mode='HTML'
            )
            success_count += 1
        except Exception as e:
            # Пользователь мог заблокировать бота
            fail_count += 1
            logging.error(f"BROADCAST_ERROR: Failed to send message to {user_id}: {e}")
    
    # 5. Отправляем отчет администратору
    await message.answer(
        f"✅ Рассылка завершена.\n"
        f"Всего получателей (из базы): {len(target_user_ids)}\n"
        f"Успешно отправлено: {success_count}\n"
        f"Неудачно (бот заблокирован/ошибка): {fail_count}"
    )
    logging.info(f"ADMIN_BROADCAST_REPORT: Total: {len(target_user_ids)}, Success: {success_count}, Fail: {fail_count}")


@dp.message()
async def forward_all_messages(message: types.Message):
    """
    Обрабатывает любые сообщения (текст, фото, стикеры и т.д.), 
    которые не были перехвачены другими обработчиками, и пересылает 
    их администратору, а также сохраняет ID пользователя.
    """
    
    # --- ЛОГИРОВАНИЕ: Получение произвольного сообщения ---
    log_text = message.text[:50] if message.text else f"Non-text message: {message.content_type}"
    logging.info(f"USER_EVENT: ARBITRARY_MESSAGE | Content: '{log_text}' | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")
    # ------------------------------------------------------
    
    # Сохраняем ID пользователя в Firestore (если он не администратор)
    if str(message.from_user.id) != ADMIN_ID:
        await save_user_id(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )

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
    Инициализирует Firebase и запускает веб-сервер для обработки вебхуков.
    """
    # Инициализация Firebase перед запуском бота
    init_firebase()
    
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
