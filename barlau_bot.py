import asyncio
import random
import string
import os
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from referral_system import register_user, add_referral_bonus, get_referral_balance, init_db

API_TOKEN = '8010342563:AAHjVpmEA8NifsIP3NaQO2HtKi1Zj5qb1d4'
ADMIN_ID = 1904069791

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
init_db()

class EditField(StatesGroup):
    waiting_for_value = State()

user_query_balance = {}
user_pending_codes = {}
user_tariff = {}
user_requests = {}
user_admin_messages = {}
editing_field = {}
user_active_requests = {}
admin_current_request = None
admin_queue = []
admin_current_request = None  # ID текущего запроса
bot_enabled = True  # Флаг активности бота

# ===== Вспомогательные =====

def format_report(req):
    parts = []
    if "phone" in req:
        parts.append(f"├ 📱 Телефон: <b>{req['phone']}</b>")
    if "operator" in req:
        parts.append(f"├ 🏢 Оператор: {req['operator']}")
    if "region" in req:
        parts.append(f"├ 🏙️ Регион: {req['region']}")
    if "country" in req:
        parts.append(f"└ 🌍 Страна: {req['country']}")

    if any(k in req for k in ["fio", "birthdate", "age"]):
        parts.append("\n👤 <b>Основные данные</b>")
        if "fio" in req:
            parts.append(f"├ 🧑‍💼 ФИО: {req['fio']}")
        if "birthdate" in req:
            parts.append(f"├ 🎂 Дата рождения: {req['birthdate']}")
        if "age" in req:
            parts.append(f"└ 📅 Возраст: {req['age']}")

    if "contacts" in req and req["contacts"]:
        parts.append("\n🔎 <b>Контакты</b>")
        for contact in req["contacts"]:
            parts.append(f"├ {contact}")

    if "emails" in req and req["emails"]:
        parts.append("\n✉️ <b>Почты</b>")
        for email in req["emails"]:
            parts.append(f"├ {email}")

    if "socials" in req and req["socials"]:
        parts.append("\n🌐 <b>Соцсети</b>")
        for social in req["socials"]:
            parts.append(f"├ {social}")

    return "\n".join(parts) if parts else "Нет данных."

def generate_unique_code():
    digits = ''.join(random.choices(string.digits, k=3))
    letter = random.choice(string.ascii_uppercase)
    return digits + letter

def get_user_query_balance(user_id):
    return user_query_balance.get(user_id, 0)

def decrease_user_balance(user_id):
    if user_id in user_query_balance and user_query_balance[user_id] > 0:
        user_query_balance[user_id] -= 1

def add_user_balance(user_id, count, tariff_name):
    user_query_balance[user_id] = user_query_balance.get(user_id, 0) + count
    user_tariff[user_id] = tariff_name

def is_valid_query(text):
    if re.match(r"^\+?7\d{10}$", text) or re.match(r"^8\d{10}$", text):
        return True
    if text.startswith("https://vk.com/") or text.startswith("https://instagram.com/") or text.startswith("https://t.me/") or text.startswith("t.me/"):
        return True
    if re.match(r"^[А-Яа-яЁё\s\-]+\d{1,2}\.\d{1,2}(\.\d{4})?$", text.replace(" ", "")):
        return True
    return False

# ===== Меню кнопки =====
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    user_id = msg.from_user.id
    ref_id = msg.get_args()

    if ref_id and ref_id.isdigit() and int(ref_id) != user_id:
        register_user(user_id, int(ref_id))
    else:
        register_user(user_id)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("👤 Мой профиль", "💳 Пополнить баланс")
    kb.row("🚀 Выбрать подписку")
    await msg.answer(
        "👋 Добро пожаловать в BARLAU бот!\n\n"
        "📂 <b>Категории запроса:</b>\n"
        "🗂️ ФИО (Фамилия Имя Отчество 01.01.1990)\n"
        "📱 Номер телефона (+79001234567 или 89001234567)\n"
        "📘 VK (ссылка: https://vk.com/id...)\n"
        "✈️ Telegram (ID / username)\n"
        "📸 Instagram (ссылка: https://instagram.com/...)\n\n"
        "🔽 Используйте кнопки ниже для управления профилем.",
        reply_markup=kb
    )

@dp.message_handler(commands=['off'])
async def turn_off(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        global bot_enabled
        bot_enabled = False
        await msg.answer("⛔ Бот отключён. Пользователям будет показано сообщение о техработах.")

@dp.message_handler(commands=['on'])
async def turn_on(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        global bot_enabled
        bot_enabled = True
        await msg.answer("✅ Бот снова включён.")

@dp.message_handler(lambda msg: msg.text == "\U0001F464 Мой профиль")
async def profile(msg: types.Message):
    user_id = msg.from_user.id
    balance = get_user_query_balance(user_id)
    plan = user_tariff.get(user_id, "не активирован")
    referral_balance = get_referral_balance(user_id)
    referral_link = f"https://t.me/BARLAU_infobot?start={user_id}"
    await msg.answer(
        f"👤 Ваш профиль:\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📦 Тариф: {plan}\n"
        f"📊 Осталось запросов: {balance}\n\n"
        f"👥 <b>Реферальная система</b>\n"
        f"💰 Баланс: <b>{referral_balance} руб.</b>\n"
        f"🔗 Ваша ссылка: {referral_link}\n"
        f"Пригласите друзей и получите 10% от их пополнений!"
    )

@dp.message_handler(lambda msg: msg.text == "\U0001F4B3 Пополнить баланс")
async def balance(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Card", callback_data="pay_card"))
    kb.add(InlineKeyboardButton("💸 Crypto", callback_data="pay_coming"))
    await msg.answer("Выберите способ оплаты:", reply_markup=kb)

@dp.message_handler(lambda msg: msg.text == "\U0001F680 Выбрать подписку")
async def subscription(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("MINI (3 запроса) – 125₽", callback_data="buy_mini"))
    kb.add(InlineKeyboardButton("STANDARD (10 запросов) – 299₽", callback_data="buy_standard"))
    kb.add(InlineKeyboardButton("PRO (30 запросов) – 599₽", callback_data="buy_pro"))
    await msg.answer("📦 Выберите тариф:", reply_markup=kb)

# ===== Оплата =====
@dp.callback_query_handler(lambda c: c.data == "pay_card")
async def pay_card(call: types.CallbackQuery):
    await subscription(call.message)

@dp.callback_query_handler(lambda c: c.data == "pay_coming")
async def pay_coming(call: types.CallbackQuery):
    await call.message.answer("❌ Крипта временно недоступна.")

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def handle_buy(call: types.CallbackQuery):
    plan = call.data.split("_")[1]
    price = {"mini": 125, "standard": 299, "pro": 599}[plan]
    count = {"mini": 3, "standard": 10, "pro": 30}[plan]
    user_id = call.from_user.id
    code = generate_unique_code()
    user_pending_codes[user_id] = (code, count, plan.upper())

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data=f"confirm_payment_{user_id}"))
    await call.message.answer(
        f"💳 Оплатите <b>{price}₽</b> на карту <code>2200701915563891</code>\n"
        f"Обязательно укажите в комментарии: <code>{code}</code>\n\n"
        f"После оплаты нажмите кнопку ниже.", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_payment_"))
async def confirm_payment(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[2])
    code, count, plan = user_pending_codes.get(user_id, (None, None, None))
    if code:
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approvepay_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"declinepay_{user_id}")
        )
        await bot.send_message(
            ADMIN_ID,
            f"💳 Новый платёж\nID: <code>{user_id}</code>\nТариф: {plan}\nЗапросов: {count}\nКод: <code>{code}</code>",
            reply_markup=kb)
        await call.message.answer("⏳ Ожидайте подтверждения от администратора.")
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("approvepay_"))
async def approve_pay(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    if user_id in user_pending_codes:
        _, count, plan = user_pending_codes.pop(user_id)
        add_user_balance(user_id, count, plan)
        await bot.send_message(user_id, f"✅ Оплата подтверждена! Вам доступно {count} запросов.")
        await call.message.edit_text("✅ Оплата подтверждена.")

@dp.callback_query_handler(lambda c: c.data.startswith("declinepay_"))
async def decline_pay(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    if user_id in user_pending_codes:
        user_pending_codes.pop(user_id)
        await bot.send_message(user_id, "❌ Оплата отклонена.")
        await call.message.edit_text("❌ Оплата отклонена.")

user_active_requests = {}
user_admin_messages = {}
admin_queue = []
admin_current_request = None
data_edited = {}
user_active_requests = {}
user_admin_messages = {}
admin_queue = []
admin_current_request = None
data_edited = {}
editing_field = {}

@dp.message_handler(lambda msg: msg.text and not msg.text.startswith('/'))
async def check_enabled(msg: types.Message):
    if not bot_enabled and msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ Ведутся технические работы. Попробуйте позже.")

@dp.message_handler(content_types=['text', 'document'])
async def handle_query(msg: types.Message):
    user_id = msg.from_user.id

    state = dp.current_state(chat=msg.chat.id, user=msg.from_user.id)
    current_state = await state.get_state()
    if current_state == "EditField:waiting_for_value":
        return

    if user_id == ADMIN_ID:
        return

    if get_user_query_balance(user_id) <= 0:
        await msg.answer("❌ У вас закончились запросы.")
        return

    if user_id in user_active_requests:
        await msg.answer("⏳ У вас уже есть активный запрос. Дождитесь завершения предыдущего.")
        return

    # Сначала проверяем валидность запроса
    if msg.content_type == types.ContentType.TEXT:
        text = msg.text.strip()
        if not is_valid_query(text):
            await msg.answer("❌ Боту не известен формат вашего запроса.")
            return
        user_requests[user_id] = {"text": text}

    elif msg.content_type == types.ContentType.DOCUMENT:
        user_requests[user_id] = {"file_id": msg.document.file_id}

    # Только теперь помечаем пользователя активным и списываем запрос
    user_active_requests[user_id] = True
    decrease_user_balance(user_id)

    await msg.answer("⏳ Ваш запрос поставлен в очередь.\n🕐 Обработка обычно занимает 5–10 минут.")

    admin_queue.append(user_id)

    if not admin_current_request:
        await process_next_request()

def generate_admin_keyboard(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{user_id}"))
    kb.add(InlineKeyboardButton("✅ Найдено", callback_data=f"approve_ready_{user_id}"))
    kb.add(InlineKeyboardButton("❌ Завершить запрос", callback_data=f"close_request_{user_id}"))
    return kb

@dp.callback_query_handler(lambda c: c.data.startswith("edit_"))
async def edit_request(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    editing_field[call.from_user.id] = user_id
    await call.message.answer("✏️ Введите исправленный текст или отправьте новый файл:")
    await EditField.waiting_for_value.set()
    await call.answer()

@dp.message_handler(content_types=['text', 'document'], state=None)
async def prevent_unedited_message(msg: types.Message):
    admin_id = msg.from_user.id
    if admin_id == ADMIN_ID and admin_id not in editing_field:
        await msg.answer("⚠️ Сначала нажмите '✏️ Редактировать', прежде чем отправлять данные.")
        return

@dp.message_handler(content_types=['text', 'document'], state=EditField.waiting_for_value)
async def save_edit(msg: types.Message, state: FSMContext):
    admin_id = msg.from_user.id
    user_id = editing_field.get(admin_id)

    if not user_id:
        await msg.answer("⚠️ Нет активного редактирования.")
        await state.finish()
        return

    if user_id not in user_admin_messages:
        user_admin_messages[user_id] = []
    user_admin_messages[user_id].append(msg.message_id)

    if msg.content_type == types.ContentType.TEXT:
        text = msg.text.strip()
        if admin_id != ADMIN_ID and not is_valid_query(text):
            await msg.answer("❌ Боту не известен формат вашего запроса.")
            return
        user_requests[user_id]["text"] = text
        data_edited[user_id] = True

    elif msg.content_type == types.ContentType.DOCUMENT:
        user_requests[user_id]["file_id"] = msg.document.file_id
        data_edited[user_id] = True

    await msg.answer("✅ Данные обновлены. Можно нажать 'Найдено'.")
    await state.finish()

async def process_next_request():
    global admin_current_request

    if not admin_queue:
        admin_current_request = None
        return

    user_id = admin_queue.pop(0)
    admin_current_request = user_id

    req = user_requests.get(user_id)

    if req:
        kb = generate_admin_keyboard(user_id)
        queue_length = len(admin_queue) + 1
        header_text = f"📨 Новый запрос от <code>{user_id}</code> | В очереди: {queue_length}"

        if "text" in req:
            admin_msg = await bot.send_message(
                ADMIN_ID,
                f"{header_text}\n\n<pre>{req['text']}</pre>",
                reply_markup=kb
            )
        elif "file_id" in req:
            admin_msg = await bot.send_document(
                ADMIN_ID,
                req["file_id"],
                caption=header_text,
                reply_markup=kb
            )

        user_admin_messages[user_id] = [admin_msg.message_id]
    else:
        admin_current_request = None
        await process_next_request()

data_sent = {}

@dp.callback_query_handler(lambda c: c.data.startswith("approve_ready_"))
async def send_result(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[2])

    if user_id not in data_edited or not data_edited[user_id]:
        await call.message.answer("⚠️ Сначала нажмите '✏️ Редактировать' и введите данные.")
        return

    req = user_requests.get(user_id)
    if not req:
        await call.message.answer("⚠️ Запрос не найден.")
        return

    sent = False

    if "text" in req:
        await bot.send_message(
            user_id,
            f"✅ Найденные данные:\n\n{req['text']}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        sent = True
        del req["text"]

    if "file_id" in req:
        await bot.send_document(user_id, req["file_id"], caption="✅ Найденный отчёт")
        sent = True
        del req["file_id"]

    if sent:
        data_sent[user_id] = True
        await call.message.answer(f"✅ Данные отправлены пользователю {user_id}.")

    try:
        await call.message.edit_reply_markup(reply_markup=generate_admin_keyboard(user_id))
    except Exception:
        pass

    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("close_request_"))
async def close_request(call: types.CallbackQuery):
    global admin_current_request

    user_id = int(call.data.split("_")[2])

    if user_id not in data_sent or not data_sent[user_id]:
        await call.message.answer("⚠️ Сначала нажмите '✅ Найдено', чтобы завершить запрос.")
        return

    # остальная часть завершения
    if user_id in user_requests:
        user_requests.pop(user_id)
    if user_id in user_active_requests:
        user_active_requests.pop(user_id)
    if user_id in data_edited:
        data_edited.pop(user_id)
    if user_id in data_sent:
        data_sent.pop(user_id)
    if user_id in editing_field:
        editing_field.pop(user_id)

    if user_id in user_admin_messages:
        for msg_id in user_admin_messages[user_id]:
            try:
                await bot.delete_message(ADMIN_ID, msg_id)
            except Exception:
                pass
        user_admin_messages.pop(user_id)

    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass

    await call.message.answer("❌ Запрос завершён.")
    admin_current_request = None
    await process_next_request()

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    executor.start_polling(dp, skip_updates=True)
