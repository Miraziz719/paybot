import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import *

load_dotenv()

API_TOKEN = os.getenv("ADMIN_API_TOKEN")
ADMIN_ID = 288649486

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


class PaymentState(StatesGroup):
    linebet_id = State()
    amount = State()
    withdraw_amount = State()
    withdraw_id = State()
    phone_number = State()



async def admin_transaction_info(transaction_id: int):
    """Berilgan tranzaksiya ID bo‘yicha ma'lumotni admin botga yuborish"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            t.transaction_id, 
            t.user_id, 
            t.amount, 
            t.type, 
            t.status, 
            t.details, 
            t.created_at, 
            r.file_id, 
            r.verified
        FROM transactions t
        LEFT JOIN receipts r ON t.transaction_id = r.transaction_id
        WHERE t.transaction_id = ?;
    """, (transaction_id,))
    transaction = cursor.fetchone()
    conn.close()

    if not transaction:
        return await bot.send_message(ADMIN_ID, f"⚠ Tranzaksiya `{transaction_id}` topilmadi.")

    transaction_id, user_id, amount, trx_type, status, details, created_at, file_id, verified = transaction

    caption = (
        f"📌 *Tranzaksiya ID:* `{transaction_id}`\n"
        f"👤 *Foydalanuvchi:* `{user_id}`\n"
        f"💰 *Summasi:* `{amount}` so‘m\n"
        f"🔄 *Turi:* `{trx_type}`\n"
        f"📊 *Status:* `{status}`\n"
        f"📝 *Izoh:* `{details or 'Yo‘q'}`\n"
        f"📅 *Sana:* `{created_at}`\n"
        f"✅ *Tasdiqlangan:* {'Ha' if verified else 'Yo‘q'}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{transaction_id}_{user_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{transaction_id}_{user_id}")
        ]
    ])

    if file_id and os.path.exists(file_id):
        photo = FSInputFile(file_id)
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=caption, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await bot.send_message(ADMIN_ID, caption, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_receipt(callback: CallbackQuery):
    _, transaction_id, user_id = callback.data.split("_")
    transaction_id = int(transaction_id)
    user_id = int(user_id)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Chekni tasdiqlash (verified = TRUE)
    cursor.execute("UPDATE receipts SET verified = TRUE WHERE transaction_id = ?", (transaction_id,))
    cursor.execute(
        "UPDATE users SET balance = balance + (SELECT amount FROM transactions WHERE transaction_id = ?) WHERE user_id = ?",
        (transaction_id, user_id)
    )
    conn.commit()
    conn.close()

    await callback.answer("✅ Check tasdiqlandi!", show_alert=True)
    await bot.send_message(ADMIN_ID, f"✅ Check #{transaction_id} tasdiqlandi!")

    from user import bot as userBot
    await userBot.send_message(user_id, f"✅ Sizning to'lovingiz tasdiqlandi\n📌 Check ID: {transaction_id}")


@router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_receipt(callback: CallbackQuery):
    _, transaction_id, user_id = callback.data.split("_")
    transaction_id = int(transaction_id)
    user_id = int(user_id)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Chekni rad etish (verified = FALSE)
    cursor.execute("UPDATE receipts SET verified = FALSE WHERE transaction_id = ?", (transaction_id,))
    conn.commit()
    conn.close()

    await callback.answer("❌ Check bekor qilindi!", show_alert=True)
    await bot.send_message(ADMIN_ID, f"❌ Check #{transaction_id} bekor qilindi!")

    from user import bot as userBot
    await userBot.send_message(user_id, f"❌ Sizning to'lovingiz bekor qilindi!\n📌 Check ID: {transaction_id}")



@router.message(Command("admin_transaction"))
async def handle_admin_transaction(message: types.Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await message.answer("❗ Iltimos, tranzaksiya ID ni kiriting.\n\nMisol: `/admin_transaction 123`")

    try:
        transaction_id = int(command.args)
    except ValueError:
        return await message.answer("🚨 Noto‘g‘ri ID! Tranzaksiya ID faqat raqam bo‘lishi kerak.")

    await admin_transaction_info(transaction_id)


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        try:
            await message.answer("🏠 Bosh menyu")
        except Exception as e:
            await message.answer(f"⚠️ Xatolik: {str(e)}")
    else:
        await message.answer("⛔ Siz admin sifatida topilmadingiz!")


async def start_admin_bot():
    print("Admin bot ishga tushdi!")
    await dp.start_polling(bot)

