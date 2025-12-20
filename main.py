import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import locale # Модуль для работы с языковыми настройками

from aiogram import Bot, Dispatcher, types, F, html
from aiohttp import web # Требуется для запуска веб-сервера

# --- НАСТРОЙКА РУССКОЙ ЛОКАЛИ ---
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Russian')
    except locale.Error:
        logging.warning("Русская локаль не установлена. Названия месяцев могут быть на английском.")
# ---------------------------------

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8317813238:AAEZly_kyYMZK961uC32FVYR6xiB31XPylA") 
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
TARGET_TZ = timezone(timedelta(hours=3), name='MSK') 
ADMIN_ID = os.getenv("ADMIN_ID", "1126029973") # !!! ВАШ РЕАЛЬНЫЙ ТЕЛЕГРАМ ID !!!

# --- НАСТРОЙКА ID ПОЛЬЗОВАТЕЛЕЙ (ЖЕСТКОЕ КОДИРОВАНИЕ) ---
# !!! КРИТИЧЕСКИ ВАЖНО: ДОБАВЬТЕ СЮДА ID ВАШЕГО ОСНОВНОГО ПОЛУЧАТЕЛЯ !!!
# ID должен быть указан как ЦЕЛОЕ ЧИСЛО (без кавычек).
# ИЗМЕНЕНО: Инициализируем сразу с указанными ID пользователей.
TARGET_RECIPIENTS_IDS = {
    333121087,  # Добавлен первый пользователь
    7891228883, # Добавлен второй пользователь
}

# Автоматически добавляем ADMIN_ID в список получателей, чтобы администратор тоже мог тестировать рассылку
try:
    ADMIN_ID_INT = int(ADMIN_ID)
    TARGET_RECIPIENTS_IDS.add(ADMIN_ID_INT)
except ValueError:
    logging.error("ADMIN_ID не является целым числом.")
# -------------------------------------------------------------

# --- СООБЩЕНИЯ АДВЕНТ-КАЛЕНДАРЯ ---
ADVENT_MESSAGES = {
    # === НЕДЕЛЯ 1: СВЕТ И ЛЕГКОСТЬ ===
    1: "🗓️ Начало чуда! Сегодняшняя миссия: найди 5 вещей, которые напоминают тебе о Новом годе, и пришли мне их фото. ✨",
    2: "🎁 Твой главный подарок: знать, что моя любовь к тебе безусловна и неизменна. И я это докажу. ❤️",
    3: "🎵 Мини-задание: Включи свою самую любимую, но очень старую новогоднюю песню. И пришли мне ее название. Создаем плейлист нашего праздника! 🎶",
    4: "💫 Ты — мой личный 'Северный свет'. Ты сияешь даже в самые пасмурные дни. Спасибо за то, что ты есть. 💖",
    5: "💌 Помни о самой важной магии зимы: **\"Мечтай — и сбудется\"**. Чтобы ты никогда не забывала это простое правило, я оставил тебе кое-что. Проверь почтовый ящик, это личный талисман. 🍀",
    6: "🪞 Задание дня: Посмотри в зеркало и назови 3 свои черты, которые тебе в себе нравятся больше всего. А я назову три свои любимые черты в тебе! Твоя красота внутри и снаружи. ❤️",
    7: "🎬 Мини-отдых! Сегодня вечером наша миссия — полное расслабление. Напиши мне, какой самый уютный фильм ты хотела бы посмотреть. Я готовлю попкорн! 🍿",
    # === НЕДЕЛЯ 2: ТЕПЛО И БЛИЗОСТЬ / СОВМЕСТНОЕ ТВОРЧЕСТВО ===
    8: "👃 Закрой глаза. Подумай, какой запах для тебя самый новогодний (мандарины, ель, корица)? Пришли мне его название. Я буду представлять, что мы его чувствуем вместе. ✨", 
    9: "📸 **Время для меня:** Сделай 'селфи счастья'. Пришли мне фото, на котором ты искренне улыбаешься. Это мой личный заряд энергии! 😊",
    10: "💡 **Мой главный урок:** Ты — моя главная ценность. Я обещаю: моя открытость всегда будет твоей безопасностью. Просто знай, что ты нужна мне, такой, какая есть. 💯",
    11: "📝 **Задание дня:** Напиши 5 вещей, которые я делаю, и которые вызывают у тебя самое сильное чувство комфорта и тепла. Это поможет мне узнать тебя лучше сейчас. ✍️",
    12: "🍝 **Вечер сюрпризов:** Сегодня я надену фартук, чтобы создать уют для нас двоих! А вечером, после пасты и бокала чего-то вкусного, тебя ждет кое-что важное. Готовься к новому приключению! 🥂",
    13: "✨ **Твой день!** Сегодня ты — абсолютная звезда. Иди и сияй! Съемки пройдут великолепно, и ты увидишь себя моими глазами. Ты самая красивая! 💖",
    14: "🫂 **Мы вместе.** Иногда планы идут не так, как хочется. Но знаешь что? Это не главное. Главное — мы справимся с чем угодно. Я здесь, чтобы поддержать тебя. Наши лучшие моменты ещё впереди. Обнимаю. ❤️",
    # === НЕДЕЛЯ 3: ВОЛШЕБСТВО И УДИВЛЕНИЕ ===
    15: "🏞️ **Наше мини-приключение.** Сегодня нас ждет небольшое путешествие: старинные здания и тишина зимнего леса. Наслаждайся каждым моментом, но помни: самое волшебное и теплое, что мы возьмем с собой — это мы сами. ❤️",
    16: "🎁Сегодня задание с наградой! Собери пазл на любой сложности (https://grandgames.net/puzzle/online/u_yolki__1), пришли мне итоговую картинку и ссылку на маркетплейс на штучку, которая сделала бы наш отпускной вечер в доме уютнее и сделала бы нас ближе💕",
    17: "🎁Сюрприз! Ты получила право на мини-сюрприз. Я реализую его тогда, когда ты захочешь. Время и день неважны, можешь запланировать заранее, а можешь написать мне посради ночи, что хочешь сюрприз и я все сделаю🦆",
    18: "🧎🧎‍♀️‍➡️Послевкусие. Все идет не так, как мы хотим, но все в наших руках. Мы можем все бросить, а можем вместе построить наше счастье и уют. А сегодня проведи вечер с семьей. После бури всегда нужна тишь и спокойствие. Сделай все дела, освободись и просто побудь хотя бы полчасика наедине с кошкой, без стороннего шума. А я попробую подарить вам немного новогоднего настроения. И да, ты мне нужна, даже если я не нужен тебе.",
    19: "🪞День-зеркало! Сегодня ты делаешь послание мне🙈",
    20: "🎁Подарок! Завтра у тебя праздник и я хочу, чтобы ты чувствовала себя королевой (хотя для меня ты всегда королева и я очень люблю твою натуральность). Выгляни в подъезд - там притаился маленький помощник для создания твоего образа. Хочу, чтобы твой день начался с улыбки💇‍♀️",
    21: "🥂Удачного праздника! Уверен, ты сегодня как обычно самая милая и красивая. Наслаждайся вечером и своей новой прической! За нас не тревожься, я сегодня максимально спокоен и ничего тебе не испорчу. Пусть всё пройдет так, как ты хочешь✨",
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

# --- УДАЛЕНА КОМАНДА /force_save_user ---

@dp.message(F.text == "/check_users", F.from_user.id == int(ADMIN_ID))
async def cmd_check_users(message: types.Message):
    """Проверяет количество сохраненных пользователей в жестко закодированном списке."""
    logging.info(f"ADMIN_EVENT: /check_users initiated by {message.from_user.id}")
    
    # Теперь мы используем хардкодированный список
    count = len(TARGET_RECIPIENTS_IDS)
    
    if count == 0:
        report_text = "⚠️ Список получателей **пуст**! Пожалуйста, добавьте ID в переменную `TARGET_RECIPIENTS_IDS` в файле `main.py`."
    else:
        # Исключаем ADMIN_ID из подсчета, если он там есть
        actual_count = count - 1 if ADMIN_ID_INT in TARGET_RECIPIENTS_IDS else count
        
        report_text = f"✅ Обнаружено **{actual_count}** целевых получателей (помимо вас)."
        id_list = "\n".join(f"- `{id}`" for id in sorted(list(TARGET_RECIPIENTS_IDS)) if id != ADMIN_ID_INT)
        
        if id_list:
             report_text += f"\n\n**Список ID получателей:**\n{id_list}"
        else:
             report_text += "\n\n(Только ваш ADMIN_ID находится в списке.)"

    await message.answer(report_text, parse_mode='Markdown')


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение с кнопкой."""
    
    logging.info(f"USER_EVENT: START | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")

    # Логика сохранения ID удалена, так как список заполняется вручную.
    
    await message.answer(
        f"Привет! Это твой адвент-календарь на декабрь. "
        "Нажимай кнопку, чтобы открыть секрет!",
        reply_markup=get_message_button
    )

@dp.callback_query(F.data == "get_advent_message")
async def process_advent_callback(callback: types.CallbackQuery):
    """Обработка нажатия кнопки адвент-календаря."""
    
    logging.info(f"USER_EVENT: BUTTON_PRESS | Callback: {callback.data} | User ID: {callback.from_user.id} | Name: {callback.from_user.full_name}")
    
    # Логика сохранения ID удалена
    
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

    current_date = datetime.now(TARGET_TZ)
    today_day = current_date.day
    today_month = current_date.month
    
    formatted_date = current_date.strftime('%d %B')

    if today_month != 12:
        text = "😴 Еще рано, приходи 1 декабря! 😴"
    
    elif today_day > MAX_DAY:
        text = "🎉 Весь адвент-календарь уже открыт! Надеюсь, тебе понравилось! 🎉"
    
    elif today_day not in ADVENT_MESSAGES:
        text = f"😴 Послание на {formatted_date} не найдено. Проверь завтра!"
        
    else:
        message_text = ADVENT_MESSAGES.get(today_day)
        
        text = (f"🗓️ {html.bold(f'Послание на {formatted_date}:')}\n\n"
                f"{html.bold(message_text)}")
        
        logging.info(f"ADVENT_MESSAGE_SENT: Day {today_day} sent to User ID: {callback.from_user.id}")

    await callback.message.answer(text, reply_markup=get_message_button, parse_mode='HTML')
    await callback.answer()


@dp.message(F.text.startswith("/broadcast"), F.from_user.id == int(ADMIN_ID))
async def cmd_broadcast(message: types.Message):
    """
    Позволяет администратору отправить произвольное сообщение ВСЕМ жестко закодированным пользователям.
    """
    
    text_to_send = message.text.replace("/broadcast", "", 1).strip()

    if not text_to_send:
        return await message.answer("Пожалуйста, укажите текст для рассылки. Формат: /broadcast <текст>")

    # ИСПОЛЬЗУЕМ ЖЕСТКО ЗАКОДИРОВАННЫЙ СПИСОК
    target_user_ids = TARGET_RECIPIENTS_IDS
    
    if not target_user_ids:
        return await message.answer("❌ Ошибка: Список получателей пуст. Добавьте ID в `TARGET_RECIPIENTS_IDS` в файле `main.py`.")
    
    success_count = 0
    fail_count = 0
    
    for user_id in target_user_ids:
        try:
            await bot.send_message(
                chat_id=user_id, # ID уже int
                text=text_to_send,
                parse_mode='HTML'
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
            logging.error(f"BROADCAST_ERROR: Failed to send message to {user_id}: {e}")
    
    # Отправляем отчет администратору
    await message.answer(
        f"✅ Рассылка завершена.\n"
        f"Всего получателей (из списка): {len(target_user_ids)}\n"
        f"Успешно отправлено: {success_count}\n"
        f"Неудачно (бот заблокирован/ошибка): {fail_count}"
    )
    logging.info(f"ADMIN_BROADCAST_REPORT: Total: {len(target_user_ids)}, Success: {success_count}, Fail: {fail_count}")


@dp.message()
async def forward_all_messages(message: types.Message):
    """
    Обрабатывает любые сообщения и пересылает их администратору.
    """
    
    log_text = message.text[:50] if message.text else f"Non-text message: {message.content_type}"
    logging.info(f"USER_EVENT: ARBITRARY_MESSAGE | Content: '{log_text}' | User ID: {message.from_user.id} | Name: {message.from_user.full_name}")
    
    # Логика сохранения ID удалена

    try:
        if ADMIN_ID and ADMIN_ID != "ВАШ_ADMIN_ID":
            
            caption = html.bold("НОВОЕ СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ:\n")
            caption += f"ID пользователя: {html.code(message.chat.id)}\n"
            caption += f"Имя: {html.bold(message.from_user.full_name)}"
            
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=caption, 
                parse_mode='HTML'
            )
            
            await bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            
        else:
            logging.warning(f"Сообщение получено от {message.from_user.full_name} ({message.chat.id}), но ADMIN_ID не настроен для пересылки.")
            
    except Exception as e:
        logging.error(f"Ошибка при пересылке сообщения: {e}")
        await message.answer("Произошла ошибка при обработке вашего сообщения.")


# --- НАСТРОЙКА ДЛЯ RENDER (WEBHOOK) ---
async def main():
    """Запускает веб-сервер для обработки вебхуков."""
    # Инициализация Firebase удалена
    
    try:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        
        app = web.Application()
        setup_application(app, dp)
        
        SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        ).register(app, "/webhook")

        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
        logging.info(f"Starting web server on port {WEB_SERVER_PORT}")
        await site.start()
        
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logging.error(f"Error during webhook setup: {e}")
        logging.info("Falling back to polling mode...")
        await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())





