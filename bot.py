import os
from functools import wraps
import telebot
import time
import random
import threading

from telebot import types
from dotenv import load_dotenv
import re
import json, datetime


DB_FILE = "users.json"
LIKES_FILE = "likes.json"
REFS_FILE = "refs.json"

pending_questions = {}  # {user_id: target_id}
pending_answers = {}    # {user_id: (target_id, mode)}

# загрузка базы
# Загружаем базу
def load_data():
    global users, refs
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}

    if os.path.exists(REFS_FILE):
        with open(REFS_FILE, "r", encoding="utf-8") as f:
            refs = json.load(f)
    else:
        refs = {}

# ---------- сохранение базы ----------
def save_data():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)
    with open(REFS_FILE, "w", encoding="utf-8") as f:
        json.dump(refs, f, indent=4, ensure_ascii=False)


def fake_likes():
    if not users:
        return
    real_users = [uid for uid in users if not uid.startswith("fake_")]
    fake_users = [uid for uid in users if uid.startswith("fake_")]

    for fake in fake_users:
        if real_users:
            target = random.choice(real_users)
            if target not in likes:
                likes[target] = []
            if fake not in likes[target]:
                likes[target].append(fake)
    save_data()


# ---------- ФЕЙКОВЫЕ ПОЛЬЗОВАТЕЛИ ----------
def add_fake_users():
    fake_data = [
        {"name": "Аня", "age": 22, "city": "Алматы", "about": "Люблю читать книги и гулять 🥰", "chance": 0.7},
        {"name": "Дима", "age": 18, "city": "Астана", "about": "Фанат спорта и путешествий ✈️", "chance": 0.3},
        {"name": "Катя", "age": 25, "city": "Шымкент", "about": "Люблю готовить и смотреть сериалы 🍰", "chance": 0.5},
        {"name": "Игорь", "age": 21, "city": "Караганда", "about": "Работаю в IT, люблю игры 👾", "chance": 0.2},
        {"name": "Саша", "age": 21, "city": "Кокшетау", "about": "Весёлый и активный человек 🔥", "chance": 0.4},
        {"name": "Валентин", "age": 17, "city": "Астана", "about": "Люблю проводить время с компом 👾", "chance": 0.2},
        {"name": "Deni", "age": 21, "city": "Павлодар", "about": "хз че сказать ", "chance": 0.4},
        {"name": "Лариса", "age": 30, "city": "Риддер", "about": "Люблю салаты 👾", "chance": 0.2},
        {"name": "Голубь", "age": 20, "city": "Уральск", "about": "От скуки ", "chance": 0.4},
        {"name": "Сопля", "age": 19, "city": "Тараз", "about": "Норм бот 👾", "chance": 0.2},
        {"name": "Алидамир", "age": 18, "city": "Семей", "about": "Покатаемсся? ", "chance": 0.4},
        {"name": "Игорюня", "age": 21, "city": "Караганда", "about": "Хз крутой чел", "chance": 0.2},
        {"name": "Тот самый", "age": 21, "city": "Костанай", "about": "Весёлый ", "chance": 0.4},
        {"name": "Узбек", "age": 19, "city": "Актау", "about": "Работаю", "chance": 0.2},
        {"name": "палас", "age": 21, "city": "Петропавловск", "about": "Общение", "chance": 0.4},
        {"name": "Максим", "age": 20, "city": "Коктобе", "about": "Джейсон стетхем!", "chance": 0.2},
        {"name": "Сергей", "age": 21, "city": "Аксу", "about": "Люблю помидоры)", "chance": 0.4},
        {"name": "Костя)", "age": 19, "city": "Павлодар", "about": "Овощоед", "chance": 0.2},
        {"name": "Шаурма", "age": 21, "city": "Ашу", "about": "Hay gitlers!", "chance": 0.4},
        {"name": "Петя", "age": 21, "city": "Алмата", "about": "Привет го общюху!", "chance": 0.4},
        {"name": "Костян", "age": 21, "city": "Ашу", "about": "по городу", "chance": 0.4},
        {"name": "Думка", "age": 21, "city": "Ашу", "about": "Пишите у меня бан", "chance": 0.4},
    ]

    for i, profile in enumerate(fake_data, start=1):
        fake_id = f"fake_{i}"
        if fake_id not in users:
            users[fake_id] = {
                "name": profile["name"],
                "age": profile["age"],
                "city": profile["city"],
                "about": profile["about"],
                "photo": None,
                "premium": False,
                "step": "done",
                "chance": profile["chance"],  # шанс на взаимный лайк
            }
    save_data()


# ---------- запуск ----------
load_dotenv()

# Загружаем токен

# Храним профили и лайки
users = {}
likes = {}


load_data()

add_fake_users()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

user_likes = {}        # {user_id: [timestamps]}
blocked_users = {}     # {user_id: unblock_time}
invites_used = {}      # {invitee_id: inviter_id}
invite_links = {}      # {inviter_id: set(invitees)}
likes_count = {}       # {user_id: int}   
refs = {} 

LIKE_LIMIT = 5
BLOCK_TIME = 1800  # 30 минут в секундах

CHANNEL_ID = "-1002748732031"  # username канала или -100XXXXXXXXXXX
OWNER_ID = 7693086158  # <- замени на своё число после получения через /myid
ADMIN_ID = 7693086158  # замени на свой


# ---------- Проверка лимита ----------
def like_user(user_id):
    now = time.time()
    me = bot.get_me()
    bot_username = me.username

    # если есть блокировка
    if user_id in blocked_users:
        if now < blocked_users[user_id]:
            wait_time = int((blocked_users[user_id] - now) / 60)
            return f"🚫 Лимит лайков достигнут! Подождите {wait_time} мин.\n" \
                   f"Или пригласите друга, чтобы снять блокировку:\n" \
                   f"https://t.me/{bot_username}?start=invite_{user_id}"
        else:
            del blocked_users[user_id]
            likes_count[user_id] = 0

    # увеличиваем лайки
    likes_count[user_id] = likes_count.get(user_id, 0) + 1

    if likes_count[user_id] > LIKE_LIMIT:
        blocked_users[user_id] = now + BLOCK_TIME
        return f"⚠️ Ты поставил {LIKE_LIMIT} лайков!\n" \
               f"Подожди 30 минут или пригласи друга по ссылке:\n" \
               f"https://t.me/{bot_username}?start=invite_{user_id}"

    return "💖 Лайк засчитан!"



# ---------- Добавление лайка ----------
def add_like(user_id):
    now = time.time()
    user_likes.setdefault(user_id, []).append(now)


# ---------- Генерация ссылки ----------
def get_invite_link(user_id):
    return f"https://t.me/{bot.get_me().username}?start=invite_{user_id}"


# Проверка: вернёт твой id (используй в личке)
@bot.message_handler(commands=['myid'])
def cmd_myid(message):
    bot.reply_to(message, f"Твой chat.id: {message.chat.id}")

# Покажет данные бота
@bot.message_handler(commands=['whoami'])
def cmd_whoami(message):
    me = bot.get_me()
    bot.reply_to(message, f"Bot username: @{me.username}\nBot id: {me.id}")

# Диагностика канала + права бота
@bot.message_handler(commands=['check_channel'])
def cmd_check_channel(message):
    # защитим команду — только владелец
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "Только владелец может выполнять эту команду.")
        return

    try:
        chat = bot.get_chat(CHANNEL_ID)
        info = f"Channel: {getattr(chat, 'title', 'no title')}\nID: {chat.id}\nType: {chat.type}"
        bot.reply_to(message, f"OK — канал найден.\n{info}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка get_chat: {e}")
        return

    try:
        me = bot.get_me()
        member = bot.get_chat_member(CHANNEL_ID, me.id)
        bot.reply_to(message, f"Статус бота в канале: {member.status}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка get_chat_member: {e}")

# Команда публикации апдейта (только владелец)
@bot.message_handler(commands=['update'])
def cmd_update(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "Только владелец может публиковать в канал.")
        return

    version = "1.3"
    changes = [
        "✨ Добавлена система взаимных лайков",
        "🔹 Исправлены баги с анкетами",
        "🚀 Добавлены фейковые пользователи для теста"
    ]
    text = f"🚀 <b>Обновление {version}</b>\n\n" + "\n".join(changes) + "\n\nСпасибо, что вы с нами ❤️"

    try:
        bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        bot.reply_to(message, "✅ Пост опубликован в канал.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при отправке в канал: {e}")

# ---------- Команда /announce ----------
@bot.message_handler(commands=["announce"])
def announce_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У тебя нет прав на публикацию.")
        return

    msg = bot.reply_to(message, "📢 Введи <b>заголовок</b> поста:", parse_mode="HTML")
    bot.register_next_step_handler(msg, announce_get_title)


def announce_get_title(message):
    title = message.text
    msg = bot.reply_to(message, "✍️ Теперь введи <b>текст поста</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, announce_get_description, title)


def announce_get_description(message, title):
    description = message.text
    msg = bot.reply_to(message, "🔗 Если хочешь, укажи ссылку (или напиши - нет):")
    bot.register_next_step_handler(msg, announce_publish, title, description)


def announce_publish(message, title, description):
    link = message.text.strip()
    if link.lower() == "нет":
        link = None

    # Красивая кнопка
    keyboard = None
    if link:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔗 Подробнее", url=link))

    text = f"📢 <b>{title}</b>\n\n{description}"

    try:
        bot.send_message(CHANNEL_ID, text, parse_mode="HTML", reply_markup=keyboard)
        bot.reply_to(message, "✅ Пост опубликован в канал!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при публикации: {e}")

# ---------- PREMIUM ----------
def give_premium(user_id, days):
    now = datetime.datetime.now()
    end_date = now + datetime.timedelta(days=days)
    users[user_id]["premium_until"] = end_date.strftime("%Y-%m-%d %H:%M:%S")
    save_data()

def check_premium(user_id):
    data = users.get(user_id, {})
    if "premium_until" in data:
        end_date = datetime.datetime.strptime(data["premium_until"], "%Y-%m-%d %H:%M:%S")
        return datetime.datetime.now() < end_date
    return False


# ---------- ДЕКОРАТОР ПРОВЕРКИ РЕГИСТРАЦИИ ----------
def require_registration(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = str(message.chat.id)
        if user_id not in users or users[user_id].get("step") != "done":
            bot.send_message(user_id, "Сначала зарегистрируйся! Используй /start 😊")
            return
        return func(message, *args, **kwargs)
    return wrapper

# ---------- ГЛАВНОЕ МЕНЮ ----------
def main_menu(user_id):
    data = users.get(str(user_id), {})
    name_display = data.get("name", "Пользователь")
    if data.get("premium"):
        name_display = f"💎 {name_display}"  # добавляем значок премиум

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🔍 Поиск")
    keyboard.add("❤️ Мои лайки", "⭐ Кто лайкнул меня")
    keyboard.add("👤 Мой профиль", "⚙️ Настройки")
    keyboard.add("💎 Премиум")
    return keyboard


# ---------- PREMIUM КУПИТЬ ----------
# --- ОБРАБОТКА КНОПКИ ПРЕМИУМ ---
@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
@require_registration
def premium_info(message):
    user_id = str(message.chat.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("1 месяц — 50⭐", callback_data="buy_premium:1m"),
        types.InlineKeyboardButton("3 месяца — 120⭐", callback_data="buy_premium:3m"),
        types.InlineKeyboardButton("Навсегда — 300⭐", callback_data="buy_premium:life")
    )
    bot.send_message(
        user_id,
        "💎 *Премиум подписка*\n\n"
        "Доступные преимущества:\n"
        "• Видеть всех, кто лайкнул\n"
        "• Неограниченные лайки\n"
        "• Повышенный приоритет в поиске\n\n"
        "Выбери тариф 👇",
        parse_mode="Markdown",
        reply_markup=kb
    )


# --- ВЫБОР ТАРИФА ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_premium:"))
def buy_tariff(call):
    user_id = str(call.from_user.id)
    tariff = call.data.split(":")[1]

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"confirm_premium:{tariff}"))

    bot.send_message(
        user_id,
        f"Для активации тарифа *{tariff}* переведи звёзды на @abonentan ✨\n\n"
        "После перевода нажми кнопку ниже.",
        parse_mode="Markdown",
        reply_markup=kb
    )


# ---------- КОМАНДА ПРОВЕРКИ ----------
@bot.message_handler(commands=['mypremium'])
def mypremium(message):
    user_id = str(message.chat.id)
    if check_premium(user_id):
        end_date = users[user_id]["premium_until"]
        bot.send_message(message.chat.id, f"✨ У тебя активен Premium до {end_date}")
    else:
        bot.send_message(message.chat.id, "❌ У тебя нет Premium. Купи через кнопку в меню.")


# --- ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_premium:"))
def confirm_premium(call):
    user_id = str(call.from_user.id)
    tariff = call.data.split(":")[1]

    users[user_id]["premium"] = True
    users[user_id]["premium_until"] = "lifetime" if tariff == "life" else tariff
    save_data()

    bot.send_message(user_id, "🎉 Премиум активирован! Добро пожаловать 💎")

# ---------- РЕГИСТРАЦИЯ ----------
import time

LIKE_LIMIT = 5  # лимит лайков
BLOCK_TIME = 1800  # 30 минут

refs = {}  # { inviter_id: [список приглашённых] }

# --- Обработка реферальной ссылки ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    args = message.text.split()

    # переход по ссылке вида /start invite_12345
    if len(args) > 1 and args[1].startswith("invite_"):
        inviter_id = args[1].replace("invite_", "")
        if inviter_id != user_id:
            refs.setdefault(inviter_id, [])
            if user_id not in refs[inviter_id]:
                refs[inviter_id].append(user_id)
                # снимаем блокировку у пригласившего
                if inviter_id in blocked_users:
                    del blocked_users[inviter_id]
                bot.send_message(inviter_id, f"🎉 К тебе присоединился друг @{message.from_user.username or user_id}, блокировка снята!")

    # регистрация
    if user_id not in users or users[user_id].get("step") != "done":
        users[user_id] = {}
        save_data()
        bot.send_message(user_id, "Привет! Давай начнём регистрацию 😊\n\nКак тебя зовут?")
        bot.register_next_step_handler(message, get_name)
        return

    bot.send_message(user_id, "Добро пожаловать обратно!", reply_markup=main_menu(user_id))

def get_name(message):
    user_id = str(message.chat.id)
    users[user_id] = {
        "name": message.text,
        "username": message.from_user.username  # сохраняем username
    }
    save_data()
    bot.send_message(user_id, "Сколько тебе лет?")
    bot.register_next_step_handler(message, get_age)

def get_age(message):
    user_id = str(message.chat.id)
    if message.text and message.text.isdigit():
        age = int(message.text)
        if 0 < age <= 100:
            users[user_id]["age"] = age
            save_data()
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            button_geo = types.KeyboardButton("📍 Отправить местоположение", request_location=True)
            keyboard.add(button_geo)
            bot.send_message(user_id, "Из какого ты города? (можешь ввести вручную или отправить геопозицию)", reply_markup=keyboard)
            bot.register_next_step_handler(message, get_city)
            return
    bot.send_message(user_id, "⚠️ Введите правильный возраст от 1 до 100")
    bot.register_next_step_handler(message, get_age)



def get_city(message):
    user_id = str(message.chat.id)
    if message.content_type == "location":
        lat = message.location.latitude
        lon = message.location.longitude
        users[user_id]["city"] = f"📍 {lat:.4f}, {lon:.4f}"  
        save_data()
        bot.send_message(user_id, "Расскажи немного о себе ✍️", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, get_about)
        return

    if message.text and re.match(r"^[A-Za-zА-Яа-яЁё\s-]+$", message.text):
        users[user_id]["city"] = message.text.strip()
        save_data()
        bot.send_message(user_id, "Расскажи немного о себе ✍️", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, get_about)
    else:
        bot.send_message(user_id, "⚠️ Введите правильное название города (только буквы).")
        bot.register_next_step_handler(message, get_city)

def get_about(message):
    user_id = str(message.chat.id)
    users[user_id]["about"] = message.text
    save_data()
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add("⏭ Пропустить")
    bot.send_message(user_id, "Пришли фото для своей анкеты 📸\n(или нажми «Пропустить»)", reply_markup=keyboard)
    bot.register_next_step_handler(message, get_photo)

def get_photo(message):
    user_id = str(message.chat.id)
    if message.content_type == "photo":
        users[user_id]["photo"] = message.photo[-1].file_id
        users[user_id]["step"] = "done"
        save_data()
        bot.send_message(user_id, "Отлично! ✅ Регистрация завершена.", reply_markup=main_menu(user_id))
        return

    if message.text == "⏭ Пропустить":
        users[user_id]["photo"] = None
        users[user_id]["step"] = "done"
        save_data()
        bot.send_message(user_id, "Хорошо, без фото тоже можно 🙂\n✅ Регистрация завершена!", reply_markup=main_menu(user_id))
        return

    bot.send_message(user_id, "Пожалуйста, отправь фото или нажми «Пропустить» 🙂")
    bot.register_next_step_handler(message, get_photo)


# ---------- ПРОФИЛЬ И ПОИСК ----------
def profile_keyboard(user_id, liked=False):
    keyboard = types.InlineKeyboardMarkup()
    if liked:
        like_btn = types.InlineKeyboardButton("✅ Лайк поставлен", callback_data="liked")
    else:
        like_btn = types.InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{user_id}")
    keyboard.add(like_btn)
    keyboard.add(types.InlineKeyboardButton("❓ Задать анонимный вопрос", callback_data=f"ask:{user_id}"))
    keyboard.add(types.InlineKeyboardButton("➡️ Далее", callback_data="next"))
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data.startswith("like_"))
def callback_like(call):
    target_id = call.data.split("_")[1]
    liker_id = str(call.from_user.id)

    # проверка лимита лайков
    if "likes_today" not in users[liker_id]:
        users[liker_id]["likes_today"] = 0
    if users[liker_id]["likes_today"] >= 5:
        blocked_until = users[liker_id].get("blocked_until")
        if not blocked_until:
            users[liker_id]["blocked_until"] = time.time() + 1800  # 30 мин
            save_data()
            blocked_until = users[liker_id]["blocked_until"]

        if time.time() < blocked_until:
            wait_minutes = int((blocked_until - time.time()) // 60)
            invite_link = f"https://t.me/{bot.get_me().username}?start={liker_id}"
            bot.send_message(
                liker_id,
                f"⛔ У тебя превышен лимит (5 лайков). Подожди {wait_minutes} мин.\n\n"
                f"Или пригласи друга, чтобы снять блокировку:\n{invite_link}"
            )
            return

    # если всё норм → лайк
    users[liker_id]["likes_today"] += 1
    save_data()
    bot.send_message(liker_id, f"❤️ Ты поставил лайк пользователю {target_id}")

def show_profile(chat_id, user_id, viewer_id=None):
    data = users.get(str(user_id), {})
    if not data:
        bot.send_message(chat_id, "Профиль недоступен.")
        return

    premium_icon = "💎 " if data.get("premium") else ""
    caption = (
        f"{premium_icon}👤 Имя: {data.get('name', '-')}\n"
        f"🎂 Возраст: {data.get('age', '?')} лет\n"
        f"🏙️ Город: {data.get('city', '-')}\n"
        f"📝 О себе:\n{data.get('about', '-')}"
    )

    # Кнопки
    if viewer_id and str(viewer_id) == str(user_id):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("✏️ Редактировать профиль", "⬅️ В меню")
    else:
        kb = profile_keyboard(user_id)  # кнопки для чужого профиля

    photo = data.get("photo")
    if photo:
        bot.send_photo(chat_id, photo, caption=caption, reply_markup=kb)
    else:
        bot.send_message(chat_id, caption, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ask:"))
def callback_ask_question(call):
    target_id = call.data.split(":")[1]  # кому задать вопрос
    asker_id = str(call.from_user.id)

    pending_questions[asker_id] = target_id
    msg = bot.send_message(asker_id, "✍️ Напиши свой анонимный вопрос:")
    bot.register_next_step_handler(msg, process_question)

def process_question(message):
    asker_id = str(message.from_user.id)
    if asker_id not in pending_questions:
        bot.send_message(asker_id, "⚠️ Ошибка: получатель не найден.")
        return

    target_id = pending_questions.pop(asker_id)
    question_text = message.text

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✍️ Ответить анонимно", callback_data=f"answer:{asker_id}:anon"),
        types.InlineKeyboardButton("👤 Ответить с именем", callback_data=f"answer:{asker_id}:named")
    )

    bot.send_message(
        target_id,
        f"❓ Вам пришёл анонимный вопрос:\n\n{question_text}",
        reply_markup=keyboard
    )
    bot.send_message(asker_id, "✅ Вопрос отправлен!")

# ---------- ОТВЕТЫ ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("answer:"))
def callback_answer_question(call):
    _, target_id, mode = call.data.split(":")  # target_id = кто задал вопрос
    responder_id = str(call.from_user.id)

    pending_answers[responder_id] = (target_id, mode)
    msg = bot.send_message(responder_id, "✍️ Напиши свой ответ:")
    bot.register_next_step_handler(msg, process_answer)

def process_answer(message):
    responder_id = str(message.from_user.id)
    if responder_id not in pending_answers:
        bot.send_message(responder_id, "⚠️ Ошибка: не найдено кому отправить ответ.")
        return

    target_id, mode = pending_answers.pop(responder_id)
    text = message.text
    responder_name = message.from_user.first_name

    if mode == "anon":
        answer_text = f"📩 Вам пришёл ответ (анонимно):\n\n{text}"
    else:
        answer_text = f"📩 Вам пришёл ответ от {responder_name}:\n\n{text}"

    bot.send_message(target_id, answer_text)
    bot.send_message(responder_id, "✅ Ответ отправлен!")

# --- просмотренные анкеты ---
seen_profiles = {}  # {user_id: [list of viewed ids]}


# ---------- ПОИСК ----------
@bot.message_handler(func=lambda m: m.text == "🔍 Поиск")
@require_registration
def search(message):
    user_id = str(message.chat.id)

    # если юзер ещё не начинал поиск — создаём список
    if user_id not in seen_profiles:
        seen_profiles[user_id] = []

    # кандидаты: все кроме себя
    candidates = [uid for uid in users if uid != user_id]

    # убираем уже просмотренных
    candidates = [c for c in candidates if c not in seen_profiles[user_id]]

    if not candidates:
        bot.send_message(user_id, "Ты уже посмотрел все анкеты 🤷")
        return

    # берём первого из списка
    candidate_id = candidates[0]

    # добавляем в просмотренные
    seen_profiles[user_id].append(candidate_id)

    show_profile(user_id, candidate_id)


# ---------- ЛАЙКИ ----------


# ---------- ❤️ Мои лайки ----------
# Мои лайки
@bot.message_handler(func=lambda m: m.text == "❤️ Мои лайки")
def my_likes(message):
    user_id = str(message.chat.id)
    liked_users = likes.get(user_id, [])

    if not liked_users:
        bot.send_message(user_id, "У тебя пока нет лайков.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for uid in liked_users:
        data = users.get(str(uid), {})
        name = data.get("name", "Без имени")
        username = data.get("username")

        if username:  # если есть username → ссылка
            btn = types.InlineKeyboardButton(text=name, url=f"https://t.me/{username}")
        else:  # если username нет → кнопка показывает ID
            btn = types.InlineKeyboardButton(text=f"{name} (нет username)", callback_data=f"show_id_{uid}")

        keyboard.add(btn)

    bot.send_message(user_id, "Твои лайки:", reply_markup=keyboard)



@bot.message_handler(func=lambda m: m.text == "⭐ Кто лайкнул меня")
def liked_me(message):
    user_id = str(message.chat.id)
    who_liked = [uid for uid, liked in likes.items() if user_id in liked]

    if not who_liked:
        bot.send_message(user_id, "Тебя пока никто не лайкнул.")
        return

    keyboard = types.InlineKeyboardMarkup()
    for uid in who_liked:
        data = users.get(str(uid), {})
        name = data.get("name", "Без имени")
        
        # Добавляем значок премиума
        if data.get("premium"):
            name = f"💎 {name}"

        username = data.get("username")
        if username:
            btn = types.InlineKeyboardButton(text=name, url=f"https://t.me/{username}")
        else:
            btn = types.InlineKeyboardButton(text=f"{name} (нет username)", callback_data=f"show_id_{uid}")

    keyboard.add(btn)

    bot.send_message(user_id, "Твои поклонники:", reply_markup=keyboard)


# Обработчик кнопки без username (показ ID)
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_id_"))
def callback_show_id(call):
    uid = call.data.split("_")[2]
    bot.answer_callback_query(call.id, text=f"ID пользователя: {uid}")




# ---------- ПОКАЗ ПРОФИЛЯ ИЗ "КТО ЛАЙКНУЛ МЕНЯ" ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_"))
def show_fan_profile(call):
    user_id = str(call.message.chat.id)
    target_id = call.data.split("_")[1]
    show_profile(user_id, target_id)

# ---------- МОЙ ПРОФИЛЬ ----------
@bot.message_handler(func=lambda m: m.text == "👤 Мой профиль")
@require_registration
def my_profile(message):
    user_id = str(message.chat.id)
    show_profile(user_id, user_id, viewer_id=user_id)
    


# ---------- РЕДАКТИРОВАНИЕ ПРОФИЛЯ ----------
@bot.message_handler(func=lambda m: m.text == "✏️ Редактировать профиль")
@require_registration
def edit_profile(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 Изменить имя", "🎂 Изменить возраст")
    kb.add("🏙️ Изменить город", "📷 Изменить фото")
    kb.add("📖 Изменить 'О себе'")
    kb.add("⬅️ В меню")
    bot.send_message(message.chat.id, "Что хочешь изменить?", reply_markup=kb)

# ---------- ИЗМЕНЕНИЕ ДАННЫХ ----------
def set_step(user_id, step):
    users[user_id]["step"] = step
    save_data()

@bot.message_handler(func=lambda m: m.text == "📝 Изменить имя")
@require_registration
def change_name(message):
    set_step(str(message.chat.id), "edit_name")
    bot.send_message(message.chat.id, "Введи новое имя:")

@bot.message_handler(func=lambda m: users.get(str(m.chat.id), {}).get("step") == "edit_name")
def save_name(message):
    user_id = str(message.chat.id)
    users[user_id]["name"] = message.text
    set_step(user_id, "done")
    save_data()
    bot.send_message(message.chat.id, "✅ Имя обновлено!")

@bot.message_handler(func=lambda m: m.text == "🎂 Изменить возраст")
@require_registration
def change_age(message):
    set_step(str(message.chat.id), "edit_age")
    bot.send_message(message.chat.id, "Введи новый возраст:")

@bot.message_handler(func=lambda m: users.get(str(m.chat.id), {}).get("step") == "edit_age")
def save_age(message):
    user_id = str(message.chat.id)
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "Возраст должен быть числом!")
        return
    users[user_id]["age"] = int(message.text)
    set_step(user_id, "done")
    bot.send_message(message.chat.id, "✅ Возраст обновлён!")

@bot.message_handler(func=lambda m: m.text == "🏙️ Изменить город")
@require_registration
def change_city(message):
    set_step(str(message.chat.id), "edit_city")
    bot.send_message(message.chat.id, "Введи новый город:")

@bot.message_handler(func=lambda m: users.get(str(m.chat.id), {}).get("step") == "edit_city")
def save_city(message):
    user_id = str(message.chat.id)
    users[user_id]["city"] = message.text
    set_step(user_id, "done")
    bot.send_message(message.chat.id, "✅ Город обновлён!")

@bot.message_handler(func=lambda m: m.text == "📷 Изменить фото")
@require_registration
def change_photo(message):
    set_step(str(message.chat.id), "edit_photo")
    bot.send_message(message.chat.id, "Пришли новое фото:")

@bot.message_handler(content_types=["photo"])
def save_photo(message):
    user_id = str(message.chat.id)
    if users.get(user_id, {}).get("step") == "edit_photo":
        users[user_id]["photo"] = message.photo[-1].file_id
        set_step(user_id, "done")
        bot.send_message(message.chat.id, "✅ Фото обновлено!")

@bot.message_handler(func=lambda m: m.text == "📖 Изменить 'О себе'")
@require_registration
def change_about(message):
    set_step(str(message.chat.id), "edit_about")
    bot.send_message(message.chat.id, "Напиши новое описание:")

@bot.message_handler(func=lambda m: users.get(str(m.chat.id), {}).get("step") == "edit_about")
def save_about(message):
    user_id = str(message.chat.id)
    users[user_id]["about"] = message.text
    set_step(user_id, "done")
    bot.send_message(message.chat.id, "✅ Описание обновлено!")

# ---------- ОБРАБОТКА КНОПКИ "⬅️ В МЕНЮ" ----------
@bot.message_handler(func=lambda m: m.text == "⬅️ В меню")
@require_registration
def back_to_menu(message):
    user_id = str(message.chat.id)
    bot.send_message(user_id, "Главное меню:", reply_markup=main_menu(user_id))

# ---------- ОБРАБОТКА ЛАЙКОВ ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("like_"))
def like_profile(call):
    user_id = str(call.message.chat.id)
    target_id = call.data.split("_", 1)[1]

    likes.setdefault(user_id, []).append(target_id)

    target = users.get(target_id, {})
    me = users.get(user_id, {})

    # --- ссылка на меня ---
    if call.from_user.username:
        me_link = f'<a href="https://t.me/{call.from_user.username}">{me.get("name", "Пользователь")}</a>'
    else:
        me_link = f'<a href="tg://user?id={user_id}">{me.get("name", "Пользователь")}</a>'

    # --- уведомление ---
    try:
        if not str(target_id).startswith("fake_"):
            bot.send_message(
                int(target_id),
                f"💌 Твоя анкета понравилась {me_link}!",
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения {target_id}: {e}")

    # --- авто-ответ фейков ---
    if str(target_id).startswith("fake_"):
        import random
        chance = target.get("chance", 0.5)  # по умолчанию 50%
        if random.random() < chance:
            likes.setdefault(target_id, []).append(user_id)
            bot.send_message(
                user_id,
                f"🎉 У тебя взаимный лайк с {target.get('name', 'Пользователь')}!",
                parse_mode="HTML"
            )
            return

    # --- если взаимный лайк с реальным ---
    if user_id in likes.get(target_id, []):
        if call.from_user.username:
            target_link = f'<a href="https://t.me/{call.from_user.username}">{target.get("name", "Пользователь")}</a>'
        else:
            target_link = f'<a href="tg://user?id={target_id}">{target.get("name", "Пользователь")}</a>'

        bot.send_message(user_id, f"🎉 У тебя взаимный лайк с {target_link}!", parse_mode="HTML")

        if not str(target_id).startswith("fake_"):
            bot.send_message(target_id, f"🎉 У тебя взаимный лайк с {me_link}!", parse_mode="HTML")

    search(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "next")
def next_profile(call):
    search(call.message)

def schedule_fake_likes():
    fake_likes()
    threading.Timer(300, schedule_fake_likes).start()  # каждые 5 минут

schedule_fake_likes()

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    # Если это шаг для зарегистрированного next_step_handler – пропускаем
    if message.text.startswith("/"):  # только если это команда
        bot.send_message(message.chat.id, "Команда не найдена. Попробуйте /menu")

# ---------- ЗАПУСК БОТА ----------

bot.polling(none_stop=True)

