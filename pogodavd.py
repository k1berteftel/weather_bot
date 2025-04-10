import logging
import json
import os
import requests
import random
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove, Message, CallbackQuery
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from transliterate import translit
from datetime import datetime
import time

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.expanduser("bot.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
OPENWEATHER_API_KEY = "062c1bf030a998d316af4f3da0a412f6"  # Действующий API-ключ
SETTINGS_FILE = os.path.expanduser("settings.json")
COORDINATES_FILE = os.path.expanduser("coordinates.json")  # Файл для кэширования координат
WEATHER_CACHE_FILE = os.path.expanduser("weather_cache.json")  # Файл для кэширования погоды
TRUSTED_USERS_FILE = os.path.expanduser("trusted_users.json")  # Файл для списка доверенных пользователей
MESSAGES_FILE = os.path.expanduser("messages.json")  # Файл для хранения недоставленных сообщений
DEFAULT_MONITORING_INTERVAL = 10800  # 3 часа
WEATHER_CACHE_DURATION = 3600  # Кэшировать погоду на 1 час (в секундах)
MESSAGE_RETENTION_DURATION = 24 * 3600  # Хранить недоставленные сообщения 24 часа (в секундах)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
SECRET_PASSWORD = "3,141"  # Пароль для входа в скрытый режим
ADMIN_ID = "1"  # Уникальный ID администратора

# Нелепая команда для вызова меню в скрытом режиме
SECRET_MENU_COMMAND = "kukushka"

# Инструкция для новеньких пользователей в СР
SECRET_MODE_INSTRUCTIONS = """
📖 **Инструкция по работе в скрытом режиме (СР)**

Вы находитесь в скрытом режиме! Здесь вы можете обмениваться сообщениями с другими пользователями в безопасной среде. Вот основные команды и действия:

1. **/{secret_menu_command}** - Открыть меню скрытого режима. В меню вы можете выбрать контакт для общения или выйти из СР.
2. **/help** - Показать эту инструкцию повторно.
3. **/exit** - Выйти из скрытого режима. Все сообщения, связанные с СР, будут удалены.
4. **Общение с контактом**:
   - После выбора контакта (через меню или входящее сообщение) вы можете отправлять текстовые сообщения или фото.
   - Чтобы выбрать нового контакта, используйте меню (/{secret_menu_command}).

⚠️ **Важно**: Все сообщения в СР удаляются при выходе из режима. Если сообщение не доставлено в течение 24 часов, отправитель получит уведомление о недоставке.

Для выхода из СР используйте /exit. Удачного общения! 😊
""".format(secret_menu_command=SECRET_MENU_COMMAND)

# Список случайных фраз для оповещения-вызова (ОВ)
NOTIFICATION_PHRASES = [
    "Сегодня в вашем городе: Воздух шепчет о встрече!",
    "Погода за окном: Легкий ветерок зовет вас!",
    "В вашем городе: Небо намекает на разговор!",
    "Прогноз на сегодня: Облака шепчут о новостях!",
    "На улице: Солнце зовет вас к диалогу!",
    "Ваш город: Дождь нашептывает о встрече!",
    "Погода сегодня: Туман скрывает тайны!",
    "В вашем регионе: Ветер приносит вести!",
    "На улице: Звезды шепчут о новостях!",
    "Прогноз: Гроза зовет к общению!"
]

# Список случайных фраз для положительных действий (доставка сообщений, установка контакта)
POSITIVE_PHRASES = [
    "А в Сочи сейчас +30, подумайте об отдыхе!",
    "В Ялте солнечно, +28, идеально для прогулки!",
    "В Анапе +27, море зовет!",
    "В Геленджике +29, подумайте о пляже!",
    "В Крыму +26, отличный день для отдыха!",
    "В Калининграде +20, прекрасная погода для экскурсий!",
    "В Санкт-Петербурге +18, солнце радует глаз!",
    "В Казани +25, идеально для прогулки по городу!",
    "В Екатеринбурге +22, подумайте о пикнике!",
    "В Новосибирске +21, отличный день для отдыха на природе!"
]

# Список случайных фраз для отрицательных действий (сообщения не доставлены, пользователь не в сети)
NEGATIVE_PHRASES = [
    "Идет сезон дождей, готовь зонтик!",
    "На улице сильный ветер, держи шапку!",
    "Дождь зарядил надолго, планы отменяются.",
    "Туман с утра, ничего не видно.",
    "Снегопад начался, дороги замело.",
    "Гроза разыгралась, лучше остаться дома.",
    "Облака сгустились, света не видно.",
    "Погода испортилась, всё пошло не так.",
    "Мороз ударил, всё замерло на месте.",
    "Луна скрылась за тучами, ночь темна."
]

# Глобальные переменные
monitoring_enabled = False
monitoring_interval = DEFAULT_MONITORING_INTERVAL
monitoring_job = None

# Состояния ConversationHandler для погодного бота
ADD_CITY = 0

# Состояния ConversationHandler для скрытого режима
ENTER_PASSWORD, SECRET_MODE, ENTER_CONTACT_ID, CHAT_MODE, ADD_USER_STEP1, ADD_USER_STEP2, CONFIRM_CONTACT = range(7)

# Специальные названия городов
SPECIAL_CITY_NAMES = {
    "ноябрьск": "noyabrsk",
    "нью-йорк": "new york",
    "львов": "lviv",
    "одесса": "odesa"
}

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ =====
def get_cities_file(telegram_id):
    """Получение пути к файлу с городами для конкретного пользователя"""
    return os.path.expanduser(f"cities_{telegram_id}.json")

def load_cities(telegram_id):
    """Загрузка списка городов для конкретного пользователя"""
    cities_file = get_cities_file(telegram_id)
    try:
        if os.path.exists(cities_file):
            with open(cities_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки городов для {telegram_id}: {e}")
    return []

def save_cities(telegram_id, cities):
    """Сохранение списка городов для конкретного пользователя"""
    cities_file = get_cities_file(telegram_id)
    try:
        with open(cities_file, "w", encoding="utf-8") as f:
            json.dump(cities, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения городов для {telegram_id}: {e}")

def load_settings():
    """Загрузка настроек мониторинга"""
    global monitoring_enabled, monitoring_interval
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                monitoring_enabled = settings.get("monitoring_enabled", False)
                monitoring_interval = settings.get("monitoring_interval", DEFAULT_MONITORING_INTERVAL)
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")

def save_settings():
    """Сохранение настроек"""
    try:
        settings = {
            "monitoring_enabled": monitoring_enabled,
            "monitoring_interval": monitoring_interval
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")

def load_coordinates():
    """Загрузка кэшированных координат из файла"""
    try:
        if os.path.exists(COORDINATES_FILE):
            with open(COORDINATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки координат: {e}")
    return {}

def save_coordinates(coordinates):
    """Сохранение кэшированных координат"""
    try:
        with open(COORDINATES_FILE, "w", encoding="utf-8") as f:
            json.dump(coordinates, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения координат: {e}")

def load_weather_cache():
    """Загрузка кэшированных погодных данных из файла"""
    try:
        if os.path.exists(WEATHER_CACHE_FILE):
            with open(WEATHER_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки кэша погоды: {e}")
    return {}

def save_weather_cache(weather_cache):
    """Сохранение кэшированных погодных данных"""
    try:
        with open(WEATHER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(weather_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения кэша погоды: {e}")

def load_trusted_users():
    """Загрузка списка доверенных пользователей"""
    try:
        if not os.path.exists(TRUSTED_USERS_FILE):
            # Если файл не существует, создаем его с начальными данными
            initial_users = {
                "1": {
                    "telegram_id": "7750281774",  # Реальный Telegram ID пользователя
                    "in_session": False,
                    "in_secret_mode": False,
                    "message_ids": [],
                    "is_new_user": True
                }
            }
            with open(TRUSTED_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_users, f, ensure_ascii=False, indent=2)
            logger.info(f"Создан файл {TRUSTED_USERS_FILE} с начальными данными: {initial_users}")
        with open(TRUSTED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки доверенных пользователей: {e}")
        return {}

def save_trusted_users(users):
    """Сохранение списка доверенных пользователей"""
    try:
        with open(TRUSTED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения доверенных пользователей: {e}")

def load_messages():
    """Загрузка недоставленных сообщений"""
    try:
        if not os.path.exists(MESSAGES_FILE):
            # Если файл не существует, создаем пустой
            with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
            logger.info(f"Создан пустой файл {MESSAGES_FILE}")
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки сообщений: {e}")
        return {}

def save_messages(messages):
    """Сохранение недоставленных сообщений"""
    try:
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщений: {e}")

async def cleanup_old_messages(context: ContextTypes.DEFAULT_TYPE):
    """Удаление сообщений, которые старше 24 часов, и уведомление отправителей"""
    messages = load_messages()
    current_time = int(time.time())
    updated = False
    trusted_users = load_trusted_users()

    for recipient_id in list(messages.keys()):
        user_messages = messages[recipient_id]
        filtered_messages = []
        for msg in user_messages:
            if current_time - msg["timestamp"] < MESSAGE_RETENTION_DURATION:
                filtered_messages.append(msg)
            else:
                # Уведомляем отправителя о недоставке (отрицательное действие)
                sender_id = msg["sender_id"]
                sender_telegram_id = get_telegram_id(sender_id)
                if sender_telegram_id:
                    sent_message = await context.bot.send_message(
                        chat_id=sender_telegram_id,
                        text=random.choice(NEGATIVE_PHRASES)
                    )
                    if sender_id in trusted_users:
                        trusted_users[sender_id]["message_ids"] = trusted_users[sender_id].get("message_ids", []) + [sent_message.message_id]
        if len(filtered_messages) != len(user_messages):
            updated = True
            if filtered_messages:
                messages[recipient_id] = filtered_messages
            else:
                del messages[recipient_id]

    if updated:
        save_messages(messages)
        save_trusted_users(trusted_users)

# ===== ПОГОДНЫЕ ФУНКЦИИ =====
def validate_city(city):
    """Валидация названия города"""
    # Проверяем длину (минимум 3 символа) и что строка состоит только из букв и пробелов
    if len(city) < 3:
        return False
    # Разрешаем буквы (включая кириллицу), пробелы и дефисы
    if not re.match(r'^[a-zA-Zа-яА-Я\s-]+$', city):
        return False
    return True

def transliterate_city(city):
    """Транслитерация названия города с учетом исключений"""
    lower_city = city.lower()
    if lower_city in SPECIAL_CITY_NAMES:
        return SPECIAL_CITY_NAMES[lower_city]
    try:
        return translit(city, "ru", reversed=True).replace(" ", "_").lower()
    except Exception:
        return city.lower()

def get_coordinates(city):
    """Получение координат города через Nominatim с кэшированием"""
    if not validate_city(city):
        return None

    coordinates_cache = load_coordinates()
    city_lower = city.lower()

    # Проверяем, есть ли координаты в кэше
    if city_lower in coordinates_cache:
        logger.info(f"Координаты для {city} найдены в кэше: {coordinates_cache[city_lower]}")
        return coordinates_cache[city_lower]

    # Если координат нет в кэше, делаем запрос к Nominatim
    try:
        params = {"q": city, "format": "json", "limit": 1}
        headers = {"User-Agent": "WeatherBot/1.0 (pogodavd_bot@example.com)"}  # Укажи свой email
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        data = response.json()

        if data and len(data) > 0:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            coordinates = {"lat": lat, "lon": lon}
            coordinates_cache[city_lower] = coordinates
            save_coordinates(coordinates_cache)
            logger.info(f"Получены координаты для {city}: lat={lat}, lon={lon}")
            return coordinates
        else:
            logger.error(f"Не удалось найти координаты для {city}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении координат для {city}: {str(e)}")
        return None

def get_current_weather(city):
    """Получение текущей погоды с OpenWeatherMap с кэшированием"""
    if not validate_city(city):
        return f"⚠️ Название города '{city}' некорректно. Используйте только буквы, пробелы или дефисы, минимум 3 символа."

    weather_cache = load_weather_cache()
    city_lower = city.lower()
    current_time = int(time.time())

    # Проверяем, есть ли актуальные данные в кэше
    if city_lower in weather_cache:
        cached_data = weather_cache[city_lower]
        if current_time - cached_data["timestamp"] < WEATHER_CACHE_DURATION:
            logger.info(f"Погода для {city} найдены в кэше: {cached_data['weather']}")
            return cached_data["weather"]

    # Если данных нет в кэше или они устарели, делаем запрос
    coordinates = get_coordinates(city)
    if not coordinates:
        return f"⚠️ Не удалось определить координаты для города {city}. Проверьте название или попробуйте другой город."

    lat = coordinates["lat"]
    lon = coordinates["lon"]

    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code == 200:
            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            description = data["weather"][0]["description"].capitalize()

            emoji = "🌤️"
            if "ясно" in description.lower():
                emoji = "☀️"
            elif "дождь" in description.lower() or "морось" in description.lower():
                emoji = "🌧️"
            elif "снег" in description.lower():
                emoji = "❄️"

            # Используем city с большой буквы
            weather_message = (f"Погода в {city.capitalize()}:\n"
                              f"{emoji} Температура: {temp}°C\n"
                              f"Ощущается как: {feels_like}°C\n"
                              f"Состояние: {description}")

            # Сохраняем в кэш
            weather_cache[city_lower] = {
                "timestamp": current_time,
                "weather": weather_message
            }
            save_weather_cache(weather_cache)

            logger.info(f"Успешно получена погода для {city}: {temp}°C, {description}")
            return weather_message
        else:
            error_message = data.get("message", "Неизвестная ошибка")
            logger.error(f"Ошибка API OpenWeatherMap для {city}: {error_message}")
            return f"⚠️ Не удалось получить погоду для {city}. Ошибка: {error_message}"

    except Exception as e:
        logger.error(f"Ошибка API OpenWeatherMap для {city}: {str(e)}")
        return f"⚠️ Не удалось получить погоду для {city}. Ошибка: {str(e)}"

def get_forecast(city):
    """Получение прогноза на 5 дней с OpenWeatherMap"""
    if not validate_city(city):
        return f"⚠️ Название города '{city}' некорректно. Используйте только буквы, пробелы или дефисы, минимум 3 символа."

    coordinates = get_coordinates(city)
    if not coordinates:
        return f"⚠️ Не удалось определить координаты для города {city}. Проверьте название или попробуйте другой город."

    lat = coordinates["lat"]
    lon = coordinates["lon"]

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code == 200 and "list" in data:
            forecast = []
            for item in data["list"][::8][:5]:  # Берем данные каждые 24 часа (шаг 8, так как данные каждые 3 часа)
                date_str = item["dt_txt"].split()[0]
                # Преобразуем дату в объект datetime
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                # Получаем день недели (Пн, Вт, Ср и т.д.)
                day_of_week = date_obj.strftime("%a")  # Сокращенное название дня недели
                # Локализуем день недели на русский
                days_of_week = {
                    "Mon": "Пн",
                    "Tue": "Вт",
                    "Wed": "Ср",
                    "Thu": "Чт",
                    "Fri": "Пт",
                    "Sat": "Сб",
                    "Sun": "Вс"
                }
                day_of_week = days_of_week.get(day_of_week, day_of_week)

                temp = round(item["main"]["temp"])
                desc = item["weather"][0]["description"].capitalize()

                emoji = "🌤️"
                if "ясно" in desc.lower():
                    emoji = "☀️"
                elif "дождь" in desc.lower() or "морось" in desc.lower():
                    emoji = "🌧️"
                elif "снег" in desc.lower():
                    emoji = "❄️"

                forecast.append(f"{day_of_week}, {date_str}: {temp}°C {emoji}, {desc}")

            logger.info(f"Успешно получен прогноз для {city}")
            return "Прогноз на 5 дней:\n" + "\n".join(forecast)
        else:
            error_message = data.get("message", "Неизвестная ошибка")
            logger.error(f"Ошибка API OpenWeatherMap для {city}: {error_message}")
            return f"⚠️ Не удалось получить прогноз для {city}. Ошибка: {error_message}"

    except Exception as e:
        logger.error(f"Ошибка API OpenWeatherMap для {city}: {str(e)}")
        return f"⚠️ Не удалось получить прогноз для {city}. Ошибка: {str(e)}"

# ===== ФУНКЦИИ СКРЫТОГО РЕЖИМА =====
def get_user_id(telegram_id):
    """Получение уникального ID пользователя по Telegram ID"""
    trusted_users = load_trusted_users()
    for user_id, user_data in trusted_users.items():
        if user_data["telegram_id"] == str(telegram_id):
            return user_id
    return None

def get_telegram_id(user_id):
    """Получение Telegram ID по уникальному ID"""
    trusted_users = load_trusted_users()
    if user_id in trusted_users:
        return trusted_users[user_id]["telegram_id"]
    return None


async def zvon_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /zvon для входа в скрытый режим"""
    logger.info(f"Получена команда /zvon от пользователя {update.effective_user.id}")
    telegram_id = str(update.effective_user.id)
    
    # Загружаем trusted_users и проверяем, существует ли пользователь
    trusted_users = load_trusted_users()
    logger.info(f"Содержимое trusted_users: {trusted_users}")
    
    user_id = get_user_id(telegram_id)
    logger.info(f"Найден user_id для telegram_id {telegram_id}: {user_id}")
    
    if not user_id:
        logger.info(f"Пользователь с telegram_id {telegram_id} не найден в trusted_users")
        await update.message.reply_text("🖕🖕🖕")
        return ConversationHandler.END

    trusted_users[user_id]["message_ids"].append(
        update.message_id if isinstance(update, Message) else update.message.message_id)

    # Очищаем context.user_data перед началом нового СР
    context.user_data.clear()
    context.user_data["user_id"] = user_id
    context.user_data["chat_id"] = update.message.chat_id  # Сохраняем chat_id
    logger.info(f"Установлены context.user_data: user_id={user_id}, chat_id={update.message.chat_id}")
    
    answer = await update.message.reply_text("Введите пароль:")
    trusted_users[user_id]["message_ids"].append(answer.message_id)
    save_trusted_users(trusted_users)
    return ENTER_PASSWORD


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка пароля для входа в скрытый режим"""
    logger.info(f"Проверка пароля от пользователя {update.effective_user.id}")
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if user_id:
        trusted_users[user_id]["message_ids"].append(
            update.message_id if isinstance(update, Message) else update.message.message_id)
    password = update.message.text.strip()
    if password != SECRET_PASSWORD:
        await update.message.reply_text("Неверный пароль!")
        return ConversationHandler.END

    if not user_id:
        logger.error(f"user_id не найден в context.user_data: {context.user_data}")
        answer = await update.message.reply_text("Произошла ошибка. Попробуйте снова с помощью /zvon.")
        trusted_users[user_id]["message_ids"].append(answer.message_id)
        save_trusted_users(trusted_users)
        return ConversationHandler.END

    # Обновляем состояние пользователя
    trusted_users[user_id]["in_secret_mode"] = True
    trusted_users[user_id]["in_session"] = True
    trusted_users[user_id]["message_ids"] = trusted_users[user_id].get("message_ids", [])
    # Проверяем, был ли пользователь новичком (первый вход)
    is_new_user = trusted_users[user_id].get("is_new_user", True)
    if is_new_user:
        trusted_users[user_id]["is_new_user"] = False  # Отмечаем, что пользователь больше не новичок
    save_trusted_users(trusted_users)

    context.user_data["in_secret_mode"] = True
    context.user_data["chat_active"] = False
    context.user_data["current_contact"] = None
    context.user_data["has_replied"] = False

    # Показываем инструкцию для новичков
    if is_new_user:
        sent_message = await update.message.reply_text(SECRET_MODE_INSTRUCTIONS)
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)

    # Показываем входящие сообщения, если они есть
    messages = load_messages()
    if user_id in list(messages.keys()) and messages[user_id]:
        # Спрашиваем, установить ли контакт с последним отправителем
        if messages.get(user_id):
            last_sender_id = messages[user_id][-1]["sender_id"]

            context.user_data["pending_contact"] = last_sender_id
            keyboard = [
                [InlineKeyboardButton("Да", callback_data=f"confirm_contact_{last_sender_id}"),
                 InlineKeyboardButton("Нет", callback_data="decline_contact")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await update.message.reply_text(
                f"Установить контакт с ID {last_sender_id}?", reply_markup=reply_markup
            )
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)
            save_trusted_users(trusted_users)
            return CONFIRM_CONTACT
    else:
        sent_message = await update.message.reply_text(
            f"Вы вошли в скрытый режим. Используйте /kukushka для отображения меню."
        )
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return SECRET_MODE

async def confirm_contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик подтверждения установки контакта"""
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice.startswith("confirm_contact_"):
        # Показываем сообщения и сразу отправляем оповещение о доставке
        messages = load_messages()
        for msg in messages[user_id]:
            if msg["is_photo"]:
                sent_message = await context.bot.send_photo(
                    chat_id=update.callback_query.message.chat.id,
                    photo=msg["photo_id"],
                    caption=f"ID {msg['sender_id']}: [Фото]"
                )
            else:
                sent_message = await context.bot.send_message(
                    chat_id=update.callback_query.message.chat.id,
                    text=f"ID {msg['sender_id']}: {msg['message']}"
                )
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)

            # Отмечаем сообщение как доставленное и отправляем оповещение отправителю (положительное действие)
            try:
                msg["delivered"] = True
                sender_id = msg["sender_id"]
                sender_telegram_id = get_telegram_id(sender_id)
                if sender_telegram_id and not trusted_users[sender_id].get("in_secret_mode", False):
                    sent_message = await context.bot.send_message(
                        chat_id=sender_telegram_id,
                        text=random.choice(POSITIVE_PHRASES)
                    )
                    trusted_users[sender_id]["message_ids"] = trusted_users[sender_id].get("message_ids", []) + [sent_message.message_id]
            except Exception as err:
                print(err)

        # Удаляем доставленные сообщения
        messages[user_id] = [msg for msg in messages[user_id] if not msg["delivered"]]
        if not messages[user_id]:
            del messages[user_id]
        save_messages(messages)
        save_trusted_users(trusted_users)
        contact_id = choice.replace("confirm_contact_", "")
        trusted_users[user_id]["current_contact"] = contact_id
        trusted_users[user_id]["chat_active"] = True
        save_trusted_users(trusted_users)

        sent_message = await query.message.edit_text(
            f"Канал с ID {contact_id} установлен. Отправьте сообщение или используйте /kukushka для отображения меню."
        )
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return CHAT_MODE
    elif choice == "decline_contact":
        sent_message = await query.message.edit_text(
            f"Вы вошли в скрытый режим. Используйте /kukushka для отображения меню."
        )
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return SECRET_MODE

    return SECRET_MODE


async def show_secret_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_mode=None) -> int:
    """Отображение меню скрытого режима с inline-кнопками"""
    logger.info(f"Получена команда /kukushka от пользователя {update.effective_user.id}")
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if user_id:
        trusted_users[user_id]["message_ids"].append(
            update.message_id if isinstance(update, Message) else update.message.message_id)
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    # Определяем режим, если не передан явно
    if chat_mode is None:
        chat_mode = trusted_users[user_id].get("chat_active", False)

    keyboard = [
        [InlineKeyboardButton("Контакт", callback_data="secret_contact")],
        [InlineKeyboardButton("Выход", callback_data="secret_exit")]
    ]
    if user_id == ADMIN_ID:
        keyboard.insert(1, [InlineKeyboardButton("Добавить пользователя", callback_data="secret_add_user")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Всегда создаем новое сообщение с меню
    sent_message = await update.message.reply_text(
        "Выберите действие:" if not chat_mode else "Вы в режиме чата. Отправьте сообщение или выберите действие:",
        reply_markup=reply_markup
    )
    context.user_data["menu_message_id"] = sent_message.message_id
    trusted_users[user_id]["message_ids"].append(sent_message.message_id)
    save_trusted_users(trusted_users)
    return CHAT_MODE if chat_mode else SECRET_MODE


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ инструкции в скрытом режиме"""
    logger.info(f"Получена команда /help от пользователя {update.effective_user.id}")
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if user_id:
        trusted_users[user_id]["message_ids"].append(update.message_id if isinstance(update, Message) else update.message.message_id)
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    sent_message = await update.message.reply_text(SECRET_MODE_INSTRUCTIONS)
    trusted_users[user_id]["message_ids"].append(sent_message.message_id)
    save_trusted_users(trusted_users)
    return SECRET_MODE if not trusted_users[user_id].get("chat_active", False) else CHAT_MODE


async def secret_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик callback-запросов для inline-кнопок в скрытом режиме"""
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "secret_contact":
        if user_id == ADMIN_ID:
            # Показываем список всех пользователей для админа
            keyboard = [[InlineKeyboardButton(user_id, callback_data=f"contact_{user_id}")] for user_id in trusted_users.keys() if user_id != ADMIN_ID]
            keyboard.append([InlineKeyboardButton("Назад", callback_data="secret_back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await query.message.edit_text("Выберите пользователя:", reply_markup=reply_markup)
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        else:
            sent_message = await query.message.edit_text("Введите ID собеседника:")
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)
            save_trusted_users(trusted_users)
            return ENTER_CONTACT_ID
    elif choice.startswith("contact_"):
        contact_id = choice.replace("contact_", "")
        trusted_users[user_id]["current_contact"] = contact_id
        trusted_users[user_id]["chat_active"] = True
        save_trusted_users(trusted_users)

        # Отправляем уведомление собеседнику, если он не в скрытом режиме
        contact_telegram_id = trusted_users[contact_id]["telegram_id"]
        if not trusted_users[contact_id].get("in_secret_mode", False):
            notification = await context.bot.send_message(
                chat_id=contact_telegram_id,
                text=random.choice(NOTIFICATION_PHRASES)
            )
            trusted_users[contact_id]["last_notification_id"] = notification.message_id
            trusted_users[contact_id]["message_ids"] = trusted_users[contact_id].get("message_ids", []) + [notification.message_id]
            save_trusted_users(trusted_users)

        sent_message = await query.message.edit_text(f"Канал с ID {contact_id} установлен. Отправьте сообщение или используйте /kukushka для отображения меню.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return CHAT_MODE
    elif choice == "secret_back":
        sent_message = await query.message.edit_text(f"Выберите действие или используйте /kukushka для отображения меню.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return SECRET_MODE
    elif choice == "secret_add_user":
        if user_id != ADMIN_ID:
            sent_message = await query.message.reply_text("У вас нет прав для выполнения этой команды.")
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)
            save_trusted_users(trusted_users)
            return SECRET_MODE
        sent_message = await query.message.edit_text("Введите Telegram ID нового пользователя:")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return ADD_USER_STEP1
    elif choice == "secret_exit":
        return await exit_secret_mode(update.callback_query.message, context)

    return SECRET_MODE

async def enter_contact_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода ID собеседника"""
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    contact_id = update.message.text.strip()
    if contact_id not in trusted_users:
        sent_message = await update.message.reply_text("Собеседник с таким ID не найден.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return await show_secret_menu(update, context)

    if contact_id == user_id:
        sent_message = await update.message.reply_text("Вы не можете начать общение с самим собой.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return await show_secret_menu(update, context)

    trusted_users[user_id]["current_contact"] = contact_id
    trusted_users[user_id]["chat_active"] = True
    save_trusted_users(trusted_users)

    # Отправляем уведомление собеседнику, если он не в скрытом режиме
    contact_telegram_id = trusted_users[contact_id]["telegram_id"]
    if not trusted_users[contact_id].get("in_secret_mode", False):
        notification = await context.bot.send_message(
            chat_id=contact_telegram_id,
            text=random.choice(NOTIFICATION_PHRASES)
        )
        trusted_users[contact_id]["last_notification_id"] = notification.message_id
        trusted_users[contact_id]["message_ids"] = trusted_users[contact_id].get("message_ids", []) + [notification.message_id]
        save_trusted_users(trusted_users)

    sent_message = await update.message.reply_text(f"Канал с ID {contact_id} установлен. Отправьте сообщение или используйте /kukushka для отображения меню.")
    trusted_users[user_id]["message_ids"].append(sent_message.message_id)
    save_trusted_users(trusted_users)
    return CHAT_MODE

async def add_user_step1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода Telegram ID нового пользователя"""
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    telegram_id = update.message.text.strip()
    context.user_data["new_user_telegram_id"] = telegram_id
    save_trusted_users(trusted_users)

    new_user_id = str(int(list(trusted_users.keys())[-1]) + 1)

    trusted_users[new_user_id] = {
        "telegram_id": telegram_id,
        "in_session": False,
        "in_secret_mode": False,
        "message_ids": [],
        "is_new_user": True  # Отмечаем нового пользователя как новичка
    }
    save_trusted_users(trusted_users)
    sent_message = await update.message.reply_text(f"Пользователь с ID {new_user_id} добавлен.")
    trusted_users[user_id]["message_ids"].append(sent_message.message_id)
    save_trusted_users(trusted_users)
    return await show_secret_menu(update, context)


async def chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик обмена сообщениями в скрытом режиме"""
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        return ConversationHandler.END

    trusted_users[user_id]["message_ids"].append(
        update.message_id if isinstance(update, Message) else update.message.message_id)

    contact_id = trusted_users[user_id].get("current_contact")
    if not trusted_users[user_id].get("chat_active") or not contact_id:
        sent_message = await update.message.reply_text(f"Выберите контакт для общения или используйте /kukushka для отображения меню.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return SECRET_MODE

    if contact_id not in trusted_users:
        sent_message = await update.message.reply_text("Собеседник больше не доступен.")
        trusted_users[user_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)
        return await exit_secret_mode(update.message, context)

    contact_telegram_id = trusted_users[contact_id]["telegram_id"]
    message_text = update.message.text if update.message.text else None
    photo = update.message.photo[-1] if update.message.photo else None

    # Проверяем, является ли сообщение командой
    if message_text and message_text.startswith('/'):
        return CHAT_MODE  # Команда не отправляется собеседнику

    # Сохраняем сообщение как недоставленное
    messages = load_messages()
    if contact_id not in messages:
        messages[contact_id] = []

    if not trusted_users[contact_id].get("chat_active"):
        if message_text:
            messages[contact_id].append({
                "sender_id": user_id,
                "message": message_text,
                "is_photo": False,
                "photo_id": None,
                "timestamp": int(time.time()),
                "delivered": False
            })
        elif photo:
            messages[contact_id].append({
                "sender_id": user_id,
                "message": "[Фото]",
                "is_photo": True,
                "photo_id": photo.file_id,
                "timestamp": int(time.time()),
                "delivered": False
            })
        else:
            sent_message = await update.message.reply_text("Пожалуйста, отправьте текст или фото.")
            trusted_users[user_id]["message_ids"].append(sent_message.message_id)
            save_trusted_users(trusted_users)
            return CHAT_MODE
    else:
        ...

    save_messages(messages)
    await cleanup_old_messages(context)

    # Если собеседник в скрытом режиме, отправляем сообщение
    if trusted_users[contact_id].get("in_secret_mode", False):
        if message_text:
            sent_message = await context.bot.send_message(chat_id=contact_telegram_id, text=f"ID {user_id}: {message_text}")
            trusted_users[contact_id]["message_ids"].append(sent_message.message_id)
        elif photo:
            sent_message = await context.bot.send_photo(chat_id=contact_telegram_id, photo=photo.file_id, caption=f"ID {user_id}: [Фото]")
            trusted_users[contact_id]["message_ids"].append(sent_message.message_id)
        save_trusted_users(trusted_users)

    # Устанавливаем флаг, что пользователь ответил
    trusted_users[user_id]["has_replied"] = True
    save_trusted_users(trusted_users)

    return CHAT_MODE


async def exit_secret_mode(message: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершение скрытого режима"""
    if isinstance(message, Update):
        message = message.message
    else:
        ...
    logger.info(f"Получена команда /exit от пользователя {message.from_user.id}")
    trusted_users = load_trusted_users()
    user_id = context.user_data.get("user_id")
    trusted_users[user_id]["message_ids"].append(message.message_id)
    if not user_id or not trusted_users[user_id].get("in_secret_mode", False):
        save_trusted_users(trusted_users)
        return ConversationHandler.END

    chat_id = context.user_data.get("chat_id", message.chat_id)

    # Уведомляем собеседника, если он в чате
    if trusted_users[user_id].get("chat_active"):
        contact_id = trusted_users[user_id]["current_contact"]
        if contact_id in trusted_users and trusted_users[contact_id].get("in_secret_mode", False):
            contact_telegram_id = trusted_users[contact_id]["telegram_id"]
            keyboard = [[InlineKeyboardButton("Выход", callback_data="secret_exit")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await context.bot.send_message(
                chat_id=contact_telegram_id,
                text=f"Сессия окончена. ID {user_id} вышел.",
                reply_markup=reply_markup
            )
            trusted_users[contact_id]["message_ids"].append(sent_message.message_id)

                # Если пользователь ответил, отправляем ОВ отправителю
            if trusted_users[user_id].get("has_replied", False):
                sender_telegram_id = get_telegram_id(user_id)
                if sender_telegram_id and not trusted_users[user_id].get("in_secret_mode", False):
                    sent_message = await context.bot.send_message(
                        chat_id=sender_telegram_id,
                        text=random.choice(NOTIFICATION_PHRASES)
                    )
                    trusted_users[user_id]["message_ids"].append(sent_message.message_id)

    # Удаляем все сообщения, связанные с СР
    for message_id in trusted_users[user_id].get("message_ids", []):
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения {message_id} в чате {chat_id}: {e}")

    # Очищаем данные пользователя
    trusted_users[user_id]["in_secret_mode"] = False
    trusted_users[user_id]["in_session"] = False
    trusted_users[user_id]["chat_active"] = False
    trusted_users[user_id]["current_contact"] = None
    trusted_users[user_id]["has_replied"] = False
    trusted_users[user_id]["message_ids"] = []
    save_trusted_users(trusted_users)

    context.user_data.clear()
    await set_right_button(message, context)
    return ConversationHandler.END


# ===== ОСНОВНЫЕ КОМАНДЫ ПОГОДНОГО БОТА =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info("Получена команда /start")
    global monitoring_job
    await set_main_menu(context)
    load_settings()

    if monitoring_enabled and not monitoring_job:
        monitoring_job = context.job_queue.run_repeating(
            monitor_weather,
            interval=monitoring_interval,
            first=0,
            chat_id=update.message.chat_id
        )
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Добавить город(а)', callback_data='add_city')]])
    await update.message.reply_text('🌤 Доброго времени суток, бот погоды готов к работе', reply_markup=reply_markup)
    #await set_right_button(update.message, context)

async def set_main_menu(context: ContextTypes.DEFAULT_TYPE):
    """Настройка меню команд"""
    logger.info("Установка меню команд")
    commands = [
        BotCommand("start", "Перезапустить бота"),
        BotCommand("addcity", "Добавить город"),
        BotCommand("forecast", "Прогноз на 5 дней"),
        BotCommand("removecity", "Удалить город"),
        BotCommand("reset", "Сбросить все данные"),
        BotCommand("monitoron", "Включить мониторинг"),
        BotCommand("monitoroff", "Выключить мониторинг")
    ]
    await context.bot.set_my_commands(commands)

async def set_right_button(message: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка кнопки 'Добавленные города'"""
    logger.info("Установка кнопки 'Добавленные города'")
    reply_markup = ReplyKeyboardMarkup([["Добавленные города"]], resize_keyboard=True)
    await message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def monitor_weather(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическая отправка погоды"""
    chat_id = context.job.chat_id  # Получаем chat_id из объекта job
    cities = load_cities(chat_id)
    for city in cities:
        weather = get_current_weather(city)
        if "⚠️" not in weather:  # Отправляем только успешные результаты
            await context.bot.send_message(chat_id=chat_id, text=weather)

async def monitor_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включение мониторинга"""
    logger.info("Получена команда /monitoron")
    global monitoring_enabled, monitoring_job
    if monitoring_enabled:
        await update.message.reply_text("ℹ️ Мониторинг уже включен!")
        return

    monitoring_enabled = True
    save_settings()
    
    if not monitoring_job:
        monitoring_job = context.job_queue.run_repeating(
            monitor_weather,
            interval=monitoring_interval,
            first=0,
            chat_id=update.message.chat_id  # Передаем chat_id напрямую
        )
    
    await update.message.reply_text(f"✅ Мониторинг включен! Погода будет отправляться каждые {monitoring_interval // 3600} часов.")
    await set_right_button(update.message, context)

async def monitor_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выключение мониторинга"""
    logger.info("Получена команда /monitoroff")
    global monitoring_enabled, monitoring_job
    if not monitoring_enabled:
        await update.message.reply_text("ℹ️ Мониторинг уже выключен!")
        return

    monitoring_enabled = False
    save_settings()
    
    if monitoring_job:
        monitoring_job.schedule_removal()
        monitoring_job = None
    
    await update.message.reply_text("✅ Мониторинг выключен!")
    await set_right_button(update.message, context)

async def add_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления города"""
    logger.info("Получена команда /addcity")
    context.user_data['state'] = 'add_city'
    if update.message:
        await update.message.reply_text("📝 Введите название города:", reply_markup=ReplyKeyboardRemove())
    else:
        await update.callback_query.message.chat.send_message("📝 Введите название города:", reply_markup=ReplyKeyboardRemove())
    return ADD_CITY

async def save_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение нового города"""
    logger.info(f"Получено сообщение для добавления города: {update.message.text}")
    if 'state' not in context.user_data or context.user_data['state'] != 'add_city':
        logger.info("Состояние не соответствует, игнорируем сообщение")
        return -1

    city = update.message.text.strip()
    telegram_id = str(update.effective_user.id)
    cities = load_cities(telegram_id)

    if not city:
        await update.message.reply_text("❌ Название города не может быть пустым!")
        return 0

    # Сохраняем город с большой буквы
    city_display = city.capitalize()
    city_lower = city.lower()

    if city_lower in [c.lower() for c in cities]:
        await update.message.reply_text(f"⚠️ Город {city_display} уже есть в списке!")
    else:
        cities.append(city_display)  # Сохраняем с большой буквы
        save_cities(telegram_id, cities)
        weather = get_current_weather(city_display)
        await update.message.reply_text(f"✅ {city_display} добавлен!\n{weather}")

    context.user_data.pop('state', None)
    await set_right_button(update.message, context)
    return -1

async def remove_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления города"""
    logger.info("Получена команда /removecity")
    telegram_id = str(update.effective_user.id)
    cities = load_cities(telegram_id)
    if not cities:
        await update.message.reply_text("ℹ️ Нет добавленных городов для удаления.")
        return

    keyboard = [[InlineKeyboardButton(city, callback_data=f"remove_{city}")] for city in cities]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите город для удаления:", reply_markup=reply_markup)

async def confirm_remove_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления города"""
    logger.info("Подтверждение удаления города")
    query = update.callback_query
    await query.answer()
    city = query.data.replace("remove_", "")

    telegram_id = str(query.from_user.id)
    cities = load_cities(telegram_id)
    if city in cities:
        cities.remove(city)
        save_cities(telegram_id, cities)
        await query.message.reply_text(f"✅ Город {city} удален!")
    else:
        await query.message.reply_text(f"⚠️ Город {city} не найден в списке!")

    await set_right_button(query.message, context)

async def forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогноз"""
    logger.info("Получена команда /forecast")
    telegram_id = str(update.effective_user.id)
    cities = load_cities(telegram_id)
    if not cities:
        await update.message.reply_text("ℹ️ Сначала добавьте города через /addcity")
        return

    keyboard = [[InlineKeyboardButton(city, callback_data=f"forecast_{city}")] for city in cities]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите город для прогноза:", reply_markup=reply_markup)

async def show_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогноз для выбранного города"""
    logger.info("Показ прогноза для выбранного города")
    query = update.callback_query
    await query.answer()
    city = query.data.replace("forecast_", "")
    await query.message.reply_text(get_forecast(city))
    await set_right_button(query.message, context)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный сброс данных"""
    logger.info("Получена команда /reset")
    global monitoring_job
    if monitoring_job:
        monitoring_job.schedule_removal()
        monitoring_job = None

    telegram_id = str(update.effective_user.id)
    try:
        cities_file = get_cities_file(telegram_id)
        if os.path.exists(cities_file):
            os.remove(cities_file)
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
        if os.path.exists(COORDINATES_FILE):
            os.remove(COORDINATES_FILE)
        if os.path.exists(WEATHER_CACHE_FILE):
            os.remove(WEATHER_CACHE_FILE)
        if os.path.exists(TRUSTED_USERS_FILE):
            os.remove(TRUSTED_USERS_FILE)
        if os.path.exists(MESSAGES_FILE):
            os.remove(MESSAGES_FILE)
    except Exception as e:
        logger.error(f"Ошибка сброса: {e}")

    # Очищаем context.user_data
    context.user_data.clear()

    await update.message.reply_text("🔄 Все данные сброшены! Используйте /start")
    await set_right_button(update.message, context)

async def show_cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список городов"""
    logger.info("Получена команда 'Добавленные города'")
    telegram_id = str(update.effective_user.id)
    cities = load_cities(telegram_id)
    if not cities:
        await update.message.reply_text("ℹ️ Нет добавленных городов. Используйте /addcity")
        return

    keyboard = [[InlineKeyboardButton(city, callback_data=f"weather_{city}")] for city in cities]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите город:", reply_markup=reply_markup)

async def show_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать погоду для выбранного города"""
    logger.info("Показ погоды для выбранного города")
    query = update.callback_query
    await query.answer()
    city = query.data.replace("weather_", "")
    await query.message.reply_text(get_current_weather(city))
    await set_right_button(query.message, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена действия"""
    logger.info("Получена команда /cancel")
    context.user_data.pop('state', None)
    await update.message.reply_text("Действие отменено")
    await set_right_button(update.message, context)
    return -1

# ===== ОБРАБОТКА ОШИБОК =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.error(f"Произошла ошибка: {context.error}")
    if update and update.message:
        await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте снова или перезапустите бота с помощью /start.")
        await set_right_button(update.message, context)

# ===== ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ ДЛЯ ОТЛАДКИ =====
async def debug_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирование всех входящих сообщений для отладки"""
    logger.info(f"Получено сообщение: {update.message.text}")
    if 'state' not in context.user_data:
        await update.message.reply_text("ℹ️ Пожалуйста, начните диалог с помощью команды, например, /addcity или /forecast.")
        await set_right_button(update.message, context)

# ===== ЗАПУСК БОТА =====
def main():
    """Основная функция запуска"""
    logger.info("Запуск бота PogodaVD")
    # Создаем приложение
    application = Application.builder().token("7411644273:AAFET7Xz-w9iIi2D53XxPDlWWdluCKPe58s").build()

    # Обработчик ошибок
    #application.add_error_handler(error_handler)

    # Обработчики команд погодного бота
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("monitoron", monitor_on))
    application.add_handler(CommandHandler("monitoroff", monitor_off))

    # Добавление города
    application.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("addcity", add_city),
            CallbackQueryHandler(add_city, pattern='add_city')
        ],
        states={
            ADD_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_city)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Удаление города
    application.add_handler(CommandHandler("removecity", remove_city))
    application.add_handler(CallbackQueryHandler(confirm_remove_city, pattern="^remove_"))

    # Прогноз погоды
    application.add_handler(CommandHandler("forecast", forecast))
    application.add_handler(CallbackQueryHandler(show_forecast, pattern="^forecast_"))

    # Кнопка "Добавленные города"
    application.add_handler(MessageHandler(filters.Regex("^Добавленные города$"), show_cities))
    application.add_handler(CallbackQueryHandler(show_weather, pattern="^weather_"))

    # Скрытый режим
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("zvon", zvon_start)],
        states={
            ENTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SECRET_MODE: [
                CallbackQueryHandler(secret_mode_callback),
                CommandHandler(SECRET_MENU_COMMAND, show_secret_menu),
                CommandHandler("help", show_help),
                CommandHandler("exit", exit_secret_mode)
            ],
            ENTER_CONTACT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_contact_id)],
            CHAT_MODE: [
                CommandHandler("exit", exit_secret_mode),
                CommandHandler("help", show_help),
                CommandHandler(SECRET_MENU_COMMAND, show_secret_menu),
                MessageHandler(filters.TEXT | filters.PHOTO, chat_mode),
            ],
            ADD_USER_STEP1: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_step1)],
            CONFIRM_CONTACT: [CallbackQueryHandler(confirm_contact_callback)]
        },
        fallbacks=[CallbackQueryHandler(secret_mode_callback, pattern="^secret_")],
        per_message=False
    ))

    # Обработчик всех сообщений для отладки (добавлен в конец, исключаем команды)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, debug_message))

    # Запуск бота
    logger.info("Бот запущен, начинаем polling")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
