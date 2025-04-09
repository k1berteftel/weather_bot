from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler
from telegram.ext.filters import Text, Command, PHOTO
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
import asyncio
import requests
import logging
import json
import os
import pytz
import time
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger('telegram').setLevel(logging.DEBUG)

# Состояния для ConversationHandler
CHOOSING, ADDING_CITY, FORECAST_CITY, ZVON, CHECK_PASSWORD, HIDDEN_MODE, ENTER_CONTACT_ID, CHATTING = range(8)

# Файлы для хранения данных
USER_CITIES_FILE = "/root/pogodavd_bot/user_cities.json"
TRUSTED_USERS_FILE = "/root/pogodavd_bot/trusted_users.json"
MESSAGES_FILE = "/root/pogodavd_bot/messages.json"

# Глобальные словари
USER_CITIES = {}
TRUSTED_USERS = {'1236300146': '2', '978216734': '3'}  # Формат: {telegram_id: unique_id}
SESSIONS = {}  # Формат: {chat_id: {contact_id: [messages]}}
MESSAGES = {}  # Формат: {chat_id: {contact_id: [{"message": ..., "timestamp": ...}]}}

# Пароль для скрытого режима
SECRET_PASSWORD = "3,141"

# API ключи
YANDEX_API_KEY = "548a2dd4-589f-42b3-8a69-27ac1983ef5c"
OPENWEATHER_API_KEY = "4e2987c876b299b8c065e8ec192e907a"


# Функции для работы с файлами
def load_user_cities():
    logger.debug("Загрузка списка городов из файла")
    if os.path.exists(USER_CITIES_FILE):
        with open(USER_CITIES_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_user_cities(user_cities):
    logger.debug("Сохранение списка городов в файл")
    with open(USER_CITIES_FILE, 'w') as f:
        json.dump(user_cities, f)


def load_trusted_users():
    logger.debug("Загрузка списка доверенных пользователей")
    if os.path.exists(TRUSTED_USERS_FILE):
        with open(TRUSTED_USERS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_trusted_users(trusted_users):
    logger.debug("Сохранение списка доверенных пользователей")
    with open(TRUSTED_USERS_FILE, 'w') as f:
        json.dump(trusted_users, f)


def load_messages():
    logger.debug("Загрузка сообщений")
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_messages(messages):
    logger.debug("Сохранение сообщений")
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages, f)


# Инициализация данных
USER_CITIES = load_user_cities()
TRUSTED_USERS = load_trusted_users()
TRUSTED_USERS = {'1236300146': '2', '978216734': '3', '7365313189': '4'}
MESSAGES = load_messages()


# Функции для работы с API погоды
def get_coordinates(city):
    logger.debug(f"Запрос координат для города: {city}")
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Geocoding API response for {city}: {response.text}")
        data = response.json()
        if data and len(data) > 0:
            return data[0]["lat"], data[0]["lon"]
        logger.warning(f"Город {city} не найден в API")
        return None, None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе координат для {city}: {e}")
        return None, None


def get_current_weather(lat, lon):
    logger.debug(f"Запрос текущей погоды для координат: lat={lat}, lon={lon}")
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={lat}&lon={lon}&lang=ru_RU"
    headers = {"X-Yandex-Weather-Key": YANDEX_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Yandex Weather API response for lat={lat}, lon={lon}: {response.text}")
        data = response.json()
        if "fact" in data:
            temp = data["fact"]["temp"]
            condition = data["fact"]["condition"]
            condition_trans = {
                "clear": "Ясно", "partly-cloudy": "Малооблачно", "cloudy": "Облачно",
                "overcast": "Пасмурно", "light-rain": "Лёгкий дождь", "rain": "Дождь",
                "heavy-rain": "Сильный дождь", "showers": "Ливень", "snow": "Снег",
                "light-snow": "Лёгкий снег", "snow-showers": "Снегопад"
            }.get(condition, "Неизвестно")
            return f"Сейчас: {temp}°C, {condition_trans}"
        logger.warning("Данные о текущей погоде недоступны")
        return "Погода недоступна"
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе погоды для lat={lat}, lon={lon}: {e}")
        return "Погода недоступна"


def get_forecast_weather(lat, lon):
    logger.debug(f"Запрос прогноза погоды для координат: lat={lat}, lon={lon}")
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={lat}&lon={lon}&lang=ru_RU&limit=5"
    headers = {"X-Yandex-Weather-Key": YANDEX_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Yandex Weather forecast response for lat={lat}, lon={lon}: {response.text}")
        data = response.json()
        if "forecasts" in data:
            forecast = ""
            for day in data["forecasts"][:5]:
                date = day["date"]
                temp = day["parts"]["day"]["temp_avg"]
                condition = day["parts"]["day"]["condition"]
                condition_trans = {
                    "clear": "Ясно", "partly-cloudy": "Малооблачно", "cloudy": "Облачно",
                    "overcast": "Пасмурно", "light-rain": "Лёгкий дождь", "rain": "Дождь",
                    "heavy-rain": "Сильный дождь", "showers": "Ливень", "snow": "Снег",
                    "light-snow": "Лёгкий снег", "snow-showers": "Снегопад"
                }.get(condition, "Неизвестно")
                forecast += f"{date}: {temp}°C, {condition_trans}\n"
            return forecast
        logger.warning("Прогноз погоды недоступен")
        return "Прогноз недоступен"
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе прогноза для lat={lat}, lon={lon}: {e}")
        return "Прогноз недоступен"


# Функции для погодного бота
async def start(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /start от {chat_id}")
    if chat_id not in USER_CITIES or not USER_CITIES[chat_id]:
        add_city_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Добавить город", callback_data="add_city")]])
        await update.message.reply_text("Привет! Я @Pogodavdome2025_Bot.\nДобавь город для мониторинга:",
                                        reply_markup=add_city_btn)
    else:
        cities = USER_CITIES[chat_id]
        reply_markup = ReplyKeyboardMarkup([[city] for city in cities], resize_keyboard=True)
        add_city_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Добавить город", callback_data="add_city")]])
        await update.message.reply_text("Выбери город для прогноза:", reply_markup=reply_markup)
        await update.message.reply_text("Добавить новый город?", reply_markup=add_city_btn)
    return CHOOSING


async def add_city(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /addcity от {chat_id}")
    await update.message.reply_text("Введите город для добавления:")
    return ADDING_CITY


async def add_city_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите город для добавления:")
    return ADDING_CITY


async def add_city_input(update, context):
    chat_id = str(update.message.chat_id)
    city = update.message.text.lower()
    logger.info(f"Получен город для добавления от {chat_id}: {city}")
    lat, lon = get_coordinates(city)
    if lat and lon:
        current_weather = get_current_weather(lat, lon)
        if "Погода недоступна" not in current_weather:
            if chat_id not in USER_CITIES:
                USER_CITIES[chat_id] = []
            if city not in USER_CITIES[chat_id]:
                USER_CITIES[chat_id].append(city)
                await update.message.reply_text(f"Город {city} добавлен!\n{current_weather}")
                save_user_cities(USER_CITIES)
            else:
                await update.message.reply_text(f"Город {city} уже добавлен!")
        else:
            await update.message.reply_text(
                f"Не удалось получить погоду для {city}! Проверь название или повтори позже.")
    else:
        await update.message.reply_text(f"Город {city} не найден!")
    cities = USER_CITIES.get(chat_id, [])
    reply_markup = ReplyKeyboardMarkup([[c] for c in cities], resize_keyboard=True)
    add_city_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Добавить город", callback_data="add_city")]])
    await update.message.reply_text("Выбери город для прогноза:", reply_markup=reply_markup)
    await update.message.reply_text("Добавить новый город?", reply_markup=add_city_btn)
    return CHOOSING


async def remove_city(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда для удаления города от {chat_id}")
    text = update.message.text.lower()
    if text.startswith("удалить город "):
        city = text.replace("удалить город ", "")
        if chat_id in USER_CITIES and city in USER_CITIES[chat_id]:
            USER_CITIES[chat_id].remove(city)
            save_user_cities(USER_CITIES)
            await update.message.reply_text(f"Город {city} удален!")
        else:
            await update.message.reply_text(f"Город {city} не найден в вашем списке!")
    else:
        await update.message.reply_text("Используйте формат: 'удалить город Москва'")
    cities = USER_CITIES.get(chat_id, [])
    reply_markup = ReplyKeyboardMarkup([[c] for c in cities], resize_keyboard=True)
    add_city_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Добавить город", callback_data="add_city")]])
    await update.message.reply_text("Выбери город для прогноза:", reply_markup=reply_markup)
    await update.message.reply_text("Добавить новый город?", reply_markup=add_city_btn)
    return CHOOSING


async def forecast(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /forecast от {chat_id}")
    await update.message.reply_text("Введите город для прогноза:")
    return FORECAST_CITY


async def forecast_input(update, context):
    chat_id = str(update.message.chat_id)
    city = update.message.text.lower()
    logger.info(f"Получен город для прогноза от {chat_id}: {city}")
    lat, lon = get_coordinates(city)
    if lat and lon:
        forecast_weather = get_forecast_weather(lat, lon)
        await update.message.reply_text(f"Прогноз для {city}:\n{forecast_weather}")
    else:
        await update.message.reply_text(f"Город {city} не найден!")
    cities = USER_CITIES.get(chat_id, [])
    reply_markup = ReplyKeyboardMarkup([[c] for c in cities], resize_keyboard=True)
    add_city_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Добавить город", callback_data="add_city")]])
    await update.message.reply_text("Выбери город для прогноза:", reply_markup=reply_markup)
    await update.message.reply_text("Добавить новый город?", reply_markup=add_city_btn)
    return CHOOSING


async def get_weather(update, context):
    chat_id = str(update.message.chat_id)
    city = update.message.text.lower()
    logger.info(f"Получен выбор города от {chat_id}: {city}")
    if chat_id in USER_CITIES and city in USER_CITIES[chat_id]:
        lat, lon = get_coordinates(city)
        if lat and lon:
            current_weather = get_current_weather(lat, lon)
            await update.message.reply_text(current_weather)
        else:
            await update.message.reply_text("Не удалось получить погоду!")
    else:
        await update.message.reply_text("Город не в списке! Нажми кнопку ниже, чтобы добавить:",
                                        reply_markup=InlineKeyboardMarkup(
                                            [[InlineKeyboardButton("Добавить город", callback_data="add_city")]]))
    cities = USER_CITIES.get(chat_id, [])
    reply_markup = ReplyKeyboardMarkup([[c] for c in cities], resize_keyboard=True)
    await update.message.reply_text("Выбери другой город:", reply_markup=reply_markup)
    return CHOOSING


# Функции для скрытого режима
async def zvon(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /zvon от {chat_id}")
    # Проверяем, есть ли пользователь в списке доверенныхs
    if chat_id not in list(TRUSTED_USERS.keys()):
        await update.message.reply_text("🖕 🖕 🖕")
        return ConversationHandler.END
    await update.message.reply_text("Введите пароль:")
    return CHECK_PASSWORD


async def check_password(update, context):
    chat_id = str(update.message.chat_id)
    if update.message.text == SECRET_PASSWORD:
        if chat_id not in list(SESSIONS.keys()):
            keyboard = ReplyKeyboardMarkup([["Контакт", "Выход"]], resize_keyboard=True)
        else:
            keyboard = ReplyKeyboardMarkup([["Контакт", "Выход", "Подтвердить сессию"]], resize_keyboard=True)
        await update.message.reply_text("Добро пожаловать в скрытый режим!", reply_markup=keyboard)
        return HIDDEN_MODE
    else:
        await update.message.reply_text("Неверный пароль.")
        return ConversationHandler.END


async def hidden_mode(update, context):
    chat_id = str(update.message.chat_id)
    choice = update.message.text
    logger.info(f"Выбор в скрытом режиме от {chat_id}: {choice}")
    if choice == "Выход":
        # Очищаем сессию
        if chat_id in SESSIONS:
            contact_id = SESSIONS[chat_id]["contact_id"]
            contact_chat_id = None

            for cid, uid in TRUSTED_USERS.items():
                if uid == contact_id:
                    contact_chat_id = cid
                    break

            if contact_chat_id and contact_chat_id in SESSIONS:
                if chat_id in MESSAGES and contact_id in MESSAGES[chat_id]:
                    for msg_id in MESSAGES[chat_id][contact_id]:
                        try:
                            await context.bot.delete_message(
                                chat_id=contact_chat_id,
                                message_id=msg_id
                            )
                        except Exception as e:
                            print(f"Ошибка удаления сообщения: {e}")

                cities = USER_CITIES.get(contact_chat_id, [])
                reply_markup = ReplyKeyboardMarkup(
                    [[city] for city in cities],
                    resize_keyboard=True
                )

                await context.bot.send_message(
                    chat_id=contact_chat_id,
                    text=f"Сессия окончена. ID {TRUSTED_USERS[chat_id]} вышел.",
                    reply_markup=reply_markup
                )

                del SESSIONS[contact_chat_id]

            del SESSIONS[chat_id]

            cities = USER_CITIES.get(chat_id, [])
            reply_markup = ReplyKeyboardMarkup(
                [[city] for city in cities],
                resize_keyboard=True
            )

            await update.message.reply_text(
                "Вы вышли из скрытого режима.",
                reply_markup=reply_markup
            )
            return CHOOSING
    elif choice == "Контакт":
        await update.message.reply_text("Введите ID собеседника:")
        return ENTER_CONTACT_ID
    elif choice == "Подтвердить сессию":
        if chat_id in SESSIONS:
            contact_id = SESSIONS[chat_id]["contact_id"]
            contact_chat_id = None
            for cid, uid in TRUSTED_USERS.items():
                if uid == contact_id:
                    contact_chat_id = cid
                    break
            if contact_chat_id:
                # Показываем все сообщения
                if chat_id in MESSAGES and contact_id in MESSAGES[chat_id]:
                    for msg in MESSAGES[chat_id][contact_id]:
                        if "text" in msg:
                            await update.message.reply_text(f"ID {contact_id}: {msg['text']}")
                        elif "photo" in msg:
                            await context.bot.send_photo(chat_id=chat_id, photo=msg["photo"])
                keyboard = ReplyKeyboardMarkup([["Выход"]], resize_keyboard=True)
                await update.message.reply_text("Сессия подтверждена. Можете общаться.", reply_markup=keyboard)
                return CHATTING
        await update.message.reply_text("Нет активной сессии для подтверждения.")
        return HIDDEN_MODE
    else:
        await update.message.reply_text("Выберите 'Контакт', 'Подтвердить сессию' или 'Выход'.")
        return HIDDEN_MODE


async def enter_contact_id(update, context):
    chat_id = str(update.message.chat_id)
    contact_id = update.message.text
    logger.info(f"Получен ID собеседника от {chat_id}: {contact_id}")
    # Проверяем, есть ли такой ID в доверенных
    contact_chat_id = None
    for cid, uid in TRUSTED_USERS.items():
        if uid == contact_id:
            contact_chat_id = cid
            break
    if contact_chat_id:
        SESSIONS[chat_id] = {"contact_id": contact_id}
        await update.message.reply_text(f"Канал с ID {contact_id} установлен.")
        # Отправляем сигнал получателю
        cities = USER_CITIES.get(contact_chat_id, [])
        if cities:
            city = cities[0]  # Берем первый город
            lat, lon = get_coordinates(city)
            if lat and lon:
                current_weather = get_current_weather(lat, lon)
                await context.bot.send_message(chat_id=contact_chat_id,
                                               text=f"Сегодня в вашем городе: Воздух шепчет о встрече!")
        keyboard = ReplyKeyboardMarkup([["Выход"]], resize_keyboard=True)
        await update.message.reply_text("Ожидайте подтверждения сессии.", reply_markup=keyboard)
        # Уведомляем получателя
        SESSIONS[contact_chat_id] = {"contact_id": TRUSTED_USERS[chat_id]}
        await context.bot.send_message(chat_id=contact_chat_id,
                                       text="У вас новый запрос на общение. Введите /zvon, чтобы подтвердить.")
        return CHATTING
    else:
        await update.message.reply_text("ID не найден в списке доверенных.")
        keyboard = ReplyKeyboardMarkup([["Контакт", "Выход"]], resize_keyboard=True)
        await update.message.reply_text("Попробуйте снова:", reply_markup=keyboard)
        return HIDDEN_MODE


async def chat(update, context):
    chat_id = str(update.message.chat_id)
    if update.message.text == "Выход":
        return await hidden_mode(update, context)
    if chat_id not in SESSIONS:
        await update.message.reply_text("Сессия не активна.")
        return HIDDEN_MODE
    contact_id = SESSIONS[chat_id]["contact_id"]
    contact_chat_id = None
    for cid, uid in TRUSTED_USERS.items():
        if uid == contact_id:
            contact_chat_id = cid
            break
    if not contact_chat_id or contact_chat_id not in SESSIONS:
        # Сохраняем сообщение, если собеседник не в сессии
        if chat_id not in MESSAGES:
            MESSAGES[chat_id] = {}
        if contact_id not in MESSAGES[chat_id]:
            MESSAGES[chat_id][contact_id] = []
        message_data = {"timestamp": time.time()}
        if update.message.text:
            message_data["text"] = update.message.text
        elif update.message.photo:
            message_data["photo"] = update.message.photo[-1].file_id
        MESSAGES[chat_id][contact_id].append(message_data)
        save_messages(MESSAGES)
        await update.message.reply_text("Собеседник не в сессии. Сообщение сохранено и будет доставлено позже.")
    else:
        # Отправляем сообщение
        if update.message.text:
            await context.bot.send_message(chat_id=contact_chat_id,
                                           text=f"ID {TRUSTED_USERS[chat_id]}: {update.message.text}")
        elif update.message.photo:
            await context.bot.send_photo(chat_id=contact_chat_id, photo=update.message.photo[-1].file_id,
                                         caption=f"ID {TRUSTED_USERS[chat_id]}")
    return CHATTING


# Функции администрирования
async def add_user(update, context):
    chat_id = str(update.message.chat_id)
    if chat_id not in TRUSTED_USERS or TRUSTED_USERS[chat_id] != "1":
        await update.message.reply_text("Только администратор (ID 1) может добавлять пользователей.")
        return
    text = update.message.text
    if text.startswith("добавить пользователя "):
        parts = text.split()
        if len(parts) != 4:
            await update.message.reply_text("Формат: добавить пользователя <Telegram ID> <уникальный ID>")
            return
        telegram_id = parts[2]
        unique_id = parts[3]
        if telegram_id in TRUSTED_USERS:
            await update.message.reply_text("Этот Telegram ID уже зарегистрирован.")
            return
        for uid in TRUSTED_USERS.values():
            if uid == unique_id:
                await update.message.reply_text("Этот уникальный ID уже занят.")
                return
        TRUSTED_USERS[telegram_id] = unique_id
        save_trusted_users(TRUSTED_USERS)
        await update.message.reply_text(
            f"Пользователь с Telegram ID {telegram_id} и уникальным ID {unique_id} добавлен.")
    else:
        await update.message.reply_text("Формат: добавить пользователя <Telegram ID> <уникальный ID>")


# Утилитные функции
async def reset(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /reset от {chat_id}, сбрасываем состояние")
    context.user_data.clear()
    context.chat_data.clear()
    await update.message.reply_text("Состояние сброшено. Используй /start, чтобы начать заново.")
    return ConversationHandler.END


async def clear_updates(update, context):
    chat_id = str(update.message.chat_id)
    logger.info(f"Получена команда /clearupdates от {chat_id}, очищаем обновления")
    updates = await context.bot.get_updates(offset=update.update_id + 1)
    logger.debug(f"Очищено обновлений: {len(updates)}")
    await update.message.reply_text("Очередь обновлений очищена. Используй /start, чтобы начать заново.")
    return ConversationHandler.END


# Функция для удаления старых сообщений
async def delete_old_messages(context):
    current_time = time.time()
    for chat_id in list(MESSAGES.keys()):
        for contact_id in list(MESSAGES[chat_id].keys()):
            messages = MESSAGES[chat_id][contact_id]
            new_messages = [msg for msg in messages if current_time - msg["timestamp"] < 24 * 3600]
            if new_messages:
                MESSAGES[chat_id][contact_id] = new_messages
            else:
                del MESSAGES[chat_id][contact_id]
        if not MESSAGES[chat_id]:
            del MESSAGES[chat_id]
    save_messages(MESSAGES)


def main():
    logger.debug("Запуск бота")
    application = Application.builder().token("6162356175:AAGJgTaKrl0KLOd1ttfi6cH-RKryimg8RAg").build()

    application.job_queue.scheduler.configure(timezone=pytz.timezone("Europe/Moscow"))
    # Запускаем задачу для удаления старых сообщений каждые 10 минут
    application.job_queue.run_repeating(delete_old_messages, interval=600)

    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("addcity", "Добавить город для мониторинга"),
        BotCommand("forecast", "Показать прогноз на 5 дней"),
        BotCommand("zvon", "Войти в скрытый режим"),
        BotCommand("reset", "Сбросить состояние бота"),
        BotCommand("clearupdates", "Очистить очередь обновлений")
    ]

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("forecast", forecast),
            CommandHandler("addcity", add_city),
            CommandHandler("zvon", zvon)
        ],
        states={
            CHOOSING: [
                MessageHandler(Text() & ~Command(), get_weather),
                MessageHandler(Text(strings=["удалить город"]), remove_city),
                CallbackQueryHandler(add_city_callback, pattern="add_city")
            ],
            ADDING_CITY: [
                MessageHandler(Text() & ~Command(), add_city_input)
            ],
            FORECAST_CITY: [MessageHandler(Text() & ~Command(), forecast_input)
                            ],
            ZVON: [
                CommandHandler("zvon", zvon)
            ],
            CHECK_PASSWORD: [
                MessageHandler(Text() & ~Command(), check_password)
            ],
            HIDDEN_MODE: [
                MessageHandler(Text() & ~Command(), hidden_mode)
            ],
            ENTER_CONTACT_ID: [
                MessageHandler(Text() & ~Command(), enter_contact_id)
            ],
            CHATTING: [
                MessageHandler(Text() & ~Command(), chat),
                MessageHandler(filters=PHOTO, callback=chat)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("reset", reset),
            CommandHandler("clearupdates", clear_updates),
            CommandHandler("addcity", add_city),
            MessageHandler(Text(strings=["добавить пользователя "]), add_user)
        ]
    )

    application.add_handler(conv_handler)
    application.bot.set_my_commands(commands)
    application.run_polling()


if __name__ == "__main__":
    main()

