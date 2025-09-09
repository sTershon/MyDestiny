import os
from functools import wraps
import telebot
from telebot import types
from dotenv import load_dotenv
import re  # вверху файла
import json, os, datetime

DB_FILE = "users.json"
LIKES_FILE = "likes.json"

pending_questions = {}  # {user_id: target_id}
pending_answers = {}    # {user_id: (target_id, mode)}

# загрузка базы
def load_data():
    global users, likes
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    else:
        users = {}

    if os.path.exists(LIKES_FILE):
        with open(LIKES_FILE, "r", encoding="utf-8") as f:
            likes = json.load(f)
    else:
        likes = {}

# сохранение базы
def save_data():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    with open(LIKES_FILE, "w", encoding="utf-8") as f:
        json.dump(likes, f, ensure_ascii=False, indent=2)

# Загружаем токен
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Храним профили и лайки
users = {}
likes = {}


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
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    if user_id not in users or users[user_id].get("step") != "done":
        users[user_id] = {}  # создаём пустую анкету
        bot.send_message(user_id, "Привет! Давай начнём регистрацию 😊\n\nКак тебя зовут?")
        bot.register_next_step_handler(message, get_name)
    else:
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
def profile_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup()
    like_btn = types.InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{user_id}")
    keyboard.add(types.InlineKeyboardButton("❓ Задать анонимный вопрос", callback_data=f"ask:{user_id}"))
    next_btn = types.InlineKeyboardButton("➡️ Далее", callback_data="next")
    keyboard.add(like_btn, next_btn)
    return keyboard



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

# ---------- ПОИСК ----------
@bot.message_handler(func=lambda m: m.text == "🔍 Поиск")
@require_registration
def search(message):
    user_id = str(message.chat.id)
    candidates = [uid for uid in users if uid != user_id]
    if not candidates:
        bot.send_message(user_id, "Пока нет анкет для просмотра 🙂")
        return
    if user_id not in likes:
        likes[user_id] = []
    for candidate_id in candidates:
        if candidate_id not in likes[user_id]:
            show_profile(user_id, candidate_id)
            return
    bot.send_message(user_id, "Ты уже посмотрел все анкеты 🤷")


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
    target_id = call.data.split("_")[1]

    likes.setdefault(user_id, []).append(target_id)

    target = users.get(target_id, {})
    me = users.get(user_id, {})

    # --- ссылка на меня ---
    if call.from_user.username:
        me_link = f'<a href="https://t.me/{call.from_user.username}">{me.get("name", "Пользователь")}</a>'
    else:
        me_link = f'<a href="tg://user?id={user_id}">{me.get("name", "Пользователь")}</a>'

    # --- уведомление ---
    bot.send_message(
        target_id,
        f"💌 Твоя анкета понравилась {me_link}!",
        parse_mode="HTML"
    )

    # --- если взаимный лайк ---
    if user_id in likes.get(target_id, []):
        if call.from_user.username:
            target_link = f'<a href="https://t.me/{call.from_user.username}">{target.get("name", "Пользователь")}</a>'
        else:
            target_link = f'<a href="tg://user?id={target_id}">{target.get("name", "Пользователь")}</a>'

        bot.send_message(user_id, f"🎉 У тебя взаимный лайк с {target_link}!", parse_mode="HTML")
        bot.send_message(target_id, f"🎉 У тебя взаимный лайк с {me_link}!", parse_mode="HTML")

    search(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "next")
def next_profile(call):
    search(call.message)

@bot.message_handler(func=lambda message: True)
def unknown_command(message):
    # Если это шаг для зарегистрированного next_step_handler – пропускаем
    if message.text.startswith("/"):  # только если это команда
        bot.send_message(message.chat.id, "Команда не найдена. Попробуйте /menu")

# ---------- ЗАПУСК БОТА ----------
load_data()
bot.polling(none_stop=True)
