import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import locale # Модуль для работы с языковыми настройками

from aiogram import Bot, Dispatcher, types, F, html
from aiohttp import web # Требуется для запуска веб-сервера

# --- ИМПОРТЫ ДЛЯ FIREBASE ---
import firebase_admin
# ИСПОЛЬЗУЕМ credentials для явной инициализации
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
            
            # --- КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: ИСПОЛЬЗУЕМ ЯВНЫЕ УЧЕТНЫЕ ДАННЫЕ (Service Account) ---
            # Создаем учетные данные на основе JSON (Service Account)
            cred = credentials.Certificate(firebase_config)
            
            # Инициализируем приложение, используя явные учетные данные
            firebase_admin.initialize_app(cred)
            # -----------------------------------------------------------------------------
            
            db = firestore.client()
            logging.info("Firebase initialized successfully. Firestore client ready.")
            return True
        except Exception as e:
            # Улучшенное логирование фатальной ошибки
            logging.error(f"FATAL ERROR: Failed to initialize Firebase Admin SDK. Persistence will not work. Error: {e}")
            logging.error("Check if __firebase_config environment variable is correctly set and contains valid service account JSON.")
            db = None # Убеждаемся, что db равно None при ошибке
            return False
    elif not firebase_admin._apps:
         logging.warning("FIREBASE_CONFIG environment variable not found. Data persistence is disabled.")
         db = None
         return False
    # Возвращаем True, если db уже установлен (для избежания повторной инициализации)
    return db is not None

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
    17: "🍿 Послание на 17-е: Предлагаю сегодня вечером просмотр фильма и никакого беспокойства :)",
    18: "☀️ Послание на 18-е: Даже в самый пасмурный день ты - моё солнце.",
    19: "🎨 Послание на 19-е: ",
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
        return await message.answer("❌ Ошибка: База данных Firebase не инициализирована. Сохранение невозможно. (Попробуйте обновить файл)")

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
