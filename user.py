import os
import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, \
    ReplyKeyboardRemove, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from admin import admin_transaction_info
from handlers import format_card_number
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from asyncio.log import logger
from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("USER_API_TOKEN")
RECEIPT_FOLDER = "receipts"
CHANNEL_ID = -1002604541411
CHANNEL_DI = -1002375805009
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

pending_timeouts = {}


class PaymentState(StatesGroup):
    phone_number = State()
    linebet_id = State()
    amount = State()
    withdraw_amount = State()
    withdraw_id = State()
    withdraw_card = State()
    waiting_for_receipt = State()


def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Hisob to'ldirish", callback_data="hisob")
    kb.button(text="💸 Pul chiqarish", callback_data="pul_chiqarish")
    kb.button(text="👨‍💻 Aloqa", callback_data="aloqa")
    kb.adjust(1)
    return kb.as_markup()

def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Telefon raqamimni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def is_receipt_uploaded(transaction_id: str) -> bool:
    with sqlite3.connect("database.db", check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT receipt_id FROM receipts WHERE transaction_id = ?", (transaction_id,))
        result = cursor.fetchone()
        return result is not None and result[0] is not None

def start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start")],  # Asosiy menyuga qaytish tugmasi
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Asosiy menyu"  # Ko'rsatkich matni
    )

def check_membership_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
             [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url="https://t.me/UZB_WINS")],
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url="https://t.me/+ykoJOOeJ40Y4MjVi")],
            [InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="check_membership")]
        ]
    )

async def check_user_membership(user_id: int) -> bool:
    try:
        channel1 = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        channel2 = await bot.get_chat_member(chat_id=CHANNEL_DI, user_id=user_id)

        return (channel1.status not in ['left', 'kicked'] and
                channel2.status not in ['left', 'kicked'])
    except Exception as e:
        logger.error(f"Kanal a'zoligini tekshirishda xato: {e}")
        return False


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # 1. Kanal a'zoligini tekshirish
    is_member = await check_user_membership(user_id)
    if not is_member:
        await message.answer("🔹 Iltimos, avval kanallarga a'zo bo'ling!",
                             reply_markup=check_membership_keyboard())
        return

    # 2. Ro'yxatdan o'tganligini tekshirish
    try:
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()

            if user_data and user_data[0]:  # Ro'yxatdan o'tgan
                await message.answer(
                    "🏠 Bosh menyu:",
                    reply_markup=main_keyboard()  # Inline keyboardni yuborish
                )
            else:  # Ro'yxatdan o'tmagan
                await message.answer(
                    "📞 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:",
                    reply_markup=contact_keyboard()
                )
                await state.set_state(PaymentState.phone_number)
    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {str(e)}")


@router.message(F.text == "/start")
async def start_handler(message: types.Message):
    # /start bosilganda ham asosiy menyuni ko'rsatish
    await cmd_start(message, state=None)

@router.callback_query(lambda c: c.data == "check_membership")
async def recheck_membership_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    try:
        is_member = await check_user_membership(user_id)

        if is_member:
            # Check if user is registered
            with sqlite3.connect("database.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,))
                user_data = cursor.fetchone()

                if user_data and user_data[0]:  # If registered
                    await callback.message.edit_text(
                        "✅ A'zolik tasdiqlandi! Quyidagi menyudan foydalaning:",
                        reply_markup=main_keyboard()
                    )
                else:  # If not registered
                    await callback.message.delete()
                    await callback.message.answer(
                        "📞 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:",
                        reply_markup=contact_keyboard()
                    )
                    # await callback.message.edit_text(
                    #     "📞 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring:",
                    #     reply_markup=contact_keyboard()
                    # )
                    await state.set_state(PaymentState.phone_number)
        else:
            current_text = callback.message.text
            new_text = "❌ Hali kanalga a'zo bo'lmagansiz! Iltimos, quyidagi kanallarga a'zo bo'ling:"
            if new_text != current_text:
                await callback.message.edit_text(
                    new_text,
                    reply_markup=check_membership_keyboard()
                )
        await callback.answer()

    except Exception as e:
        logger.error(f"Recheck handlerida xato: {e}")
        # await callback.answer("⚠️ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.", show_alert=True)


@router.message(PaymentState.phone_number)
async def process_phone_number(message: types.Message, state: FSMContext):
    if not message.contact or not message.contact.phone_number:
        await message.answer("⚠️ Iltimos, tugma orqali telefon raqamingizni yuboring.")
        return

    user_id = message.from_user.id
    phone_number = message.contact.phone_number

    try:
        with sqlite3.connect("database.db", check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (user_id, phone_number) VALUES (?, ?)",
                (user_id, phone_number)
            )
            conn.commit()

        await message.answer("✅ Ro'yxatdan o'tdingiz!", reply_markup=ReplyKeyboardRemove())
        await message.answer("🏠 Bosh menyu", reply_markup=start_keyboard())  # O'zgartirildi start tugma menu bolip turadi ----------
        await state.clear()

    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {str(e)}")


# 📌 Hisob to'ldirish
@router.callback_query(F.data == "hisob")
async def start_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📌 ID raqamingizni kiriting (6 ta raqam):")
    await state.set_state(PaymentState.linebet_id)
    await callback.answer()


@router.message(PaymentState.linebet_id)
async def process_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting!")
        return
    if len(message.text) < 6:
        await message.answer("❌ ID kamida 6 ta raqam bo'lishi kerak!")
        return
    await state.update_data(linebet_id=message.text)
    await message.answer("💰 To'lov summasini kiriting (minimal 25,000 maksimal 10,000,000 so'm):")
    await state.set_state(PaymentState.amount)


@router.message(PaymentState.amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 25000 or int(message.text) > 10000000:
        await message.answer("❌ Minimal miqdor 25,000 maksimal 10,000,000 so'm!")
        return

    data = await state.get_data()
    amount = int(message.text)

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="✅ To'ladim", callback_data=f"confirm_payment_{amount}")
    confirm_kb.button(text="❌ Bekor qilish", callback_data="cancel")
    confirm_kb.adjust(1)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT card_number, card_holder FROM settings WHERE id = 1")
    settings = cursor.fetchone()
    conn.close()

    card_number, card_holder = settings
    await message.answer(
        f"🔔 To'lov tafsilotlari:\n"
        f"ID: {data['linebet_id']}\n"
        f"Summa: {amount:,.0f} so'm\n"
        f"💳 Karta: {card_number}\n"
        f"👤 Qabul qiluvchi: {card_holder}"
    )
    await message.answer("To'lovni tasdiqlang:", reply_markup=confirm_kb.as_markup())
    await state.update_data(amount=amount)


@router.callback_query(lambda c: c.data.startswith("confirm_payment_"))
async def confirm_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    amount = int(callback.data.split('_')[-1])
    data = await state.get_data()

    try:
        with sqlite3.connect("database.db", check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO transactions 
                (user_id, amount, type, status, details) 
                VALUES (?, ?, 'deposit', 'pending', ?)""",
                (user_id, amount, f"To'lov ID: {data['linebet_id']}")
            )
            cursor.execute(
                "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            transaction_id = cursor.lastrowid
            conn.commit()

        await state.update_data(transaction_id=transaction_id)
        msg = await callback.message.edit_text(
            "📎 Iltimos, check rasm yoki PDF faylini yuboring."
            "⏳ Chekni 3 daqiqa ichida yuboring:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
            ])
        )

        await state.update_data(transaction_id=transaction_id)
        await state.set_state(PaymentState.waiting_for_receipt)

        if user_id in pending_timeouts:
            pending_timeouts[user_id].cancel()
        pending_timeouts[user_id] = asyncio.create_task(process_timeout(msg, user_id, transaction_id))

    except Exception as e:
        await callback.message.answer(f"⚠️ Xatolik: {str(e)}")
    finally:
        await callback.answer()


async def process_timeout(message: types.Message, user_id: int, transaction_id: int):
    await asyncio.sleep(180)
    try:
        with sqlite3.connect("database.db", check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET status = 'failed' WHERE transaction_id = ?",
                (transaction_id,)
            )
            conn.commit()

        await message.edit_text(
            "⌛️ Chek yuborilmadi! Jarayon bekor qilindi.",
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print(f"Xabar yangilashda xato: {e}")
    finally:
        if user_id in pending_timeouts:
            del pending_timeouts[user_id]


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()  # State ichidagi barcha ma'lumotlarni olish
    transaction_id = data.get("transaction_id")
    user_id = callback.from_user.id

    try:
        with sqlite3.connect("database.db", check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET status = 'failed' WHERE transaction_id = ?",
                (transaction_id,)
            )
            conn.commit()

    except Exception as e:
        print(f"Xabar yangilashda xato: {e}")

    if user_id in pending_timeouts:
        pending_timeouts[user_id].cancel()
        del pending_timeouts[user_id]
    await callback.message.edit_text("❌ Operatsiya bekor qilindi.", reply_markup=main_keyboard())
    await state.clear()
    await callback.answer()


# 📌 SQLite bazaga rasm yo‘lini saqlash
def save_receipt_path(transaction_id, file_id):
    with sqlite3.connect("database.db") as db:
        cursor = db.cursor()

        cursor.execute("SELECT receipt_id FROM receipts WHERE transaction_id = ?", (transaction_id,))
        existing_receipt = cursor.fetchone()

        if existing_receipt:
            cursor.execute("UPDATE receipts SET file_id = ? WHERE transaction_id = ?", (file_id, transaction_id))
        else:
            cursor.execute("INSERT INTO receipts (transaction_id, file_id) VALUES (?, ?)", (transaction_id, file_id))

        db.commit()


# 📌 Rasmni qabul qilish va yo‘lini saqlash
@router.message(PaymentState.waiting_for_receipt)
async def receive_receipt(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    transaction_id = data.get("transaction_id")

    if message.media_group_id:
        await message.answer("🚨 1 ta rasim yuborin")
        return

    if not message.photo and not message.document:
        await message.answer("🚨 Iltimos, faqat rasm yoki PDF yuboring!")
        return

    if is_receipt_uploaded(user_id):
        await message.answer("🚨 Siz allaqachon chek yuborgansiz! Qayta jo‘natish mumkin emas.")
        return

    # Rasmni saqlash
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_path = os.path.join(RECEIPT_FOLDER, f"receipt_{transaction_id}.jpg")
    os.makedirs(RECEIPT_FOLDER, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}") as resp:
            if resp.status == 200:
                with open(file_path, "wb") as f:
                    f.write(await resp.read())
            else:
                await message.answer("❌ Checkni yuklab olishda xatolik yuz berdi. Qayta urinib ko‘ring.")
                return

    save_receipt_path(transaction_id, file_path)

    with sqlite3.connect("database.db", check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE transactions SET status = 'completed' WHERE transaction_id = ?",
            (transaction_id,)
        )
        conn.commit()
    
    if user_id in pending_timeouts:
        pending_timeouts[user_id].cancel()
        del pending_timeouts[user_id]

    await state.clear()
    await message.answer(
        f"✅ Check muvaffaqiyatli qabul qilindi.\nCheck ID: {transaction_id}.\nJavobi 3 ish kuni ichida xabar beriladi."
    )

    await admin_transaction_info(transaction_id)

   





@router.callback_query(F.data == "pul_chiqarish")
async def start_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💸 Yechmoqchi bo'lgan summani kiriting (minimal 25,000 so'm, maksimal 10,000,000):")
    await state.set_state(PaymentState.withdraw_amount)
    await callback.answer()


@router.message(PaymentState.withdraw_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) < 25000 or int(message.text) > 10000000:
        await message.answer("❌ Minimal summa 25,000 maksimal 10,000,000 so'm!")
        return

    amount = int(message.text)

    try:
        await state.update_data(withdraw_amount=amount)
        await message.answer("📌 ID raqamingizni kiriting (6 ta raqam):")
        await state.set_state(PaymentState.withdraw_id)

    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {str(e)}")



@router.message(PaymentState.withdraw_id)
async def process_withdrawal_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting!")
        return
    if len(message.text) < 6:
        await message.answer("❌ ID kamida 6 ta raqam bo'lishi kerak!")
        return

    await state.update_data(withdraw_id=message.text)
    await message.answer("💳 Pul yechib olish uchun karta raqamingizni kiriting (16, 18 yoki 19 xonali):")
    await state.set_state(PaymentState.withdraw_card)


@router.message(PaymentState.withdraw_card)
async def process_withdrawal_card(message: types.Message, state: FSMContext):
    card_number = message.text.strip()

    if not card_number.isdigit() or len(card_number) not in [16, 18, 19]:
        await message.answer("❌ Iltimos, 16, 18 yoki 19 xonali plastik karta raqamini kiriting!")
        return

    await state.update_data(withdraw_card=card_number)

    data = await state.get_data()
    amount = data['withdraw_amount']
    withdraw_id = data['withdraw_id']

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_withdraw_{amount}_{withdraw_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])
    await message.answer(
        f"💳 Hisobdan yechish tafsilotlari:\n"
        f"💰 Summa: {amount:,.0f} so'm\n"
        f"📌 ID: {withdraw_id}\n"
        f"💳 Karta: {format_card_number(card_number)}\n\n"
        "✅ Tasdiqlash uchun quyidagi tugmani bosing:",
        reply_markup=confirm_kb
    )


@router.callback_query(lambda c: c.data.startswith("confirm_withdraw_"))
async def confirm_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    amount, withdraw_id = callback.data.split('_')[2:4]
    amount = int(amount)

    data = await state.get_data()
    card = data['withdraw_card']

    try:
        with sqlite3.connect("database.db", check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET balance = balance - ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
                (amount, user_id)
            )
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            user_balance = cursor.fetchone()[0]
            cursor.execute(
                """INSERT INTO transactions 
                (user_id, amount, type, status, details) 
                VALUES (?, ?, 'withdraw', 'completed', ?)""",
                (user_id, amount, (f"Yechilma ID: {withdraw_id} Karta raqami: {format_card_number(card)}"))
            )
            transaction_id = cursor.lastrowid  # Yangi qo‘shilgan transaction_id
            conn.commit()

            await callback.message.edit_text(
                f"✅ {amount:,.0f} so'm hisobingizdan yechildi!\n"
                f"💰 Hisobingizda {user_balance:,.0f} so'm qoldi\n"
                f"📌 ID: {withdraw_id}\n"
                f"📌 Tranzaksiya ID: {transaction_id}\n\n"
                "Pul tushishi 1-3 ish kunini oladi.",
                reply_markup=main_keyboard()
            )

            # ✅ Admin botga to‘liq tranzaksiya ma'lumotlari bilan xabar yuborish
            await admin_transaction_info(transaction_id)


    except Exception as e:
        await callback.message.answer(f"⚠️ Xatolik: {str(e)}")
    finally:
        await callback.answer()


@router.callback_query(F.data == "aloqa")
async def contact_handler(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Savol, shikoyat, takliflar bo`lsa bizga murojaat\n"
            " qilishingiz mumkin ,"
             "adminga yozish👇"
             "📞 @@upays_team:\n",
        reply_markup=main_keyboard()
    )
    await callback.answer()


async def start_user_bot():
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    print(f"Foydalanuvchi {bot_username} bot ishga tushdi!")

    await dp.start_polling(bot)
