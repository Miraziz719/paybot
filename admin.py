import os
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import *
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
import pytz

API_TOKEN = os.getenv("ADMIN_API_TOKEN")
# ADMIN_ID = 288649486  #Miraziz
# ADMIN_ID = 6597171902 #Demir

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ✅ Komandalarni botga o‘rnatish
async def set_commands():
    commands = [
        types.BotCommand(command="start", description="Botni ishga tushirish"),
        types.BotCommand(command="change_admin", description="Adminni o'zgartirish"),
        types.BotCommand(command="change_card", description="Karta o'zgartirish"),
        types.BotCommand(command="transaction", description="Tranzaksiyani ko'rish"),
    ]
    await bot.set_my_commands(commands)

class ChangeCardState(StatesGroup):
    waiting_for_card_number = State()
    waiting_for_card_holder = State()



async def admin_transaction_info(transaction_id: int):
    """Berilgan tranzaksiya ID bo‘yicha ma'lumotni admin botga yuborish"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    admin_id = get_admin_id()

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
    cursor.execute("SELECT balance, phone_number FROM users WHERE user_id = ?", (transaction[1],))
    user = cursor.fetchone()
    conn.close()

    if not transaction:
        return await bot.send_message(admin_id, f"⚠ Tranzaksiya `{transaction_id}` topilmadi.")

    transaction_id, user_id, amount, trx_type, status, details, created_at, file_id, verified = transaction
    balance, phone_number = user

    created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    utc_zone = pytz.utc
    created_at_utc = utc_zone.localize(created_at)
    user_timezone = pytz.timezone('Asia/Tashkent')
    created_at = created_at_utc.astimezone(user_timezone).strftime("%Y-%m-%d %H:%M:%S")

    # created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    
    caption = (
        f"📌 *Tranzaksiya ID:* `{transaction_id}`\n"
        f"👤 *Foydalanuvchi:* [{user_id}](tg://user?id={user_id})\n"
        f"💰 *Summasi:* `{amount:,.0f}` so‘m\n"
        f"🔄 *Turi:* `{trx_type}`\n"
        f"📝 *Izoh:* `{details or 'Yo‘q'}`\n"
        f"📅 *Sana:* `{created_at}`\n"
        f"📞 *Phone:* {phone_number}\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{transaction_id}_{user_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_{transaction_id}_{user_id}")
        ]
    ])

    if file_id and os.path.exists(file_id):
        photo = FSInputFile(file_id)
        await bot.send_photo(chat_id=admin_id, photo=photo, caption=caption, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await bot.send_message(admin_id, caption, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_receipt(callback: CallbackQuery):
    _, transaction_id, user_id = callback.data.split("_")
    transaction_id = int(transaction_id)
    user_id = int(user_id)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Tranzaksiya turini olish
    cursor.execute("SELECT type FROM transactions WHERE transaction_id = ?", (transaction_id,))
    transaction = cursor.fetchone()

    if not transaction:
        await callback.answer("⚠️ Tranzaksiya topilmadi!", show_alert=True)
        return

    transaction_type = transaction[0]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if transaction_type == 'deposit':
        # Chekni tasdiqlash (verified = TRUE)
        cursor.execute("UPDATE receipts SET verified = TRUE WHERE transaction_id = ?", (transaction_id,))
        cursor.execute(
            """
            UPDATE users 
            SET balance = balance + (SELECT amount FROM transactions WHERE transaction_id = ?) 
            WHERE user_id = ?
            """,
            (transaction_id, user_id)
        )
        conn.commit()
        conn.close()

        # await callback.answer("✅ Check tasdiqlandi!", show_alert=True)
        new_caption = callback.message.caption + "\n✅ Tasdiqlandi! " + now
        await bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=new_caption,
            parse_mode="Markdown",
            reply_markup=None  # Tugmalarni olib tashlash
        )

        from user import bot as userBot
        await userBot.send_message(user_id, (
            f"✅ Sizning to'lovingiz tasdiqlandi\n"
            f"📌 Check ID: {transaction_id}\n"
        ))

    else:
        conn.commit()
        conn.close()

        # await callback.answer("✅ Check tasdiqlandi!", show_alert=True)
        new_text = callback.message.text + "\n✅ Tasdiqlandi! " + now
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=None  # Tugmalarni olib tashlash
        )

        from user import bot as userBot
        await userBot.send_message(user_id, (
            f"✅ Sizning so'rovingiz tasdiqlandi\n"
            f"📌 Tranzaksiya ID: {transaction_id}\n"
        ))



@router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_receipt(callback: CallbackQuery):
    _, transaction_id, user_id = callback.data.split("_")
    transaction_id = int(transaction_id)
    user_id = int(user_id)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Tranzaksiya turini olish
    cursor.execute("SELECT type FROM transactions WHERE transaction_id = ?", (transaction_id,))
    transaction = cursor.fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not transaction:
        await callback.answer("⚠️ Tranzaksiya topilmadi!", show_alert=True)
        return

    transaction_type = transaction[0]

    if transaction_type == 'deposit':
        # Chekni rad etish (verified = FALSE)
        cursor.execute("UPDATE receipts SET verified = FALSE WHERE transaction_id = ?", (transaction_id,))
        conn.commit()
        conn.close()

        # await callback.answer("❌ Check bekor qilindi!", show_alert=True)
        new_caption = callback.message.caption + f"\n❌ Bekor qilindi! {now}"
        await bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=new_caption,
            parse_mode="Markdown",
            reply_markup=None  # Tugmalarni olib tashlash
        )

        from user import bot as userBot
        await userBot.send_message(user_id, f"❌ Sizning to'lovingiz bekor qilindi!\n📌 Check ID: {transaction_id}")
    
    else:
        cursor.execute(
            """
            UPDATE users 
            SET balance = balance + (SELECT amount FROM transactions WHERE transaction_id = ?) 
            WHERE user_id = ?
            """,
            (transaction_id, user_id)
        )
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user_balance = cursor.fetchone()
        user_balance = user_balance[0] if user_balance else 0 

        conn.commit()
        conn.close()

        # await callback.answer("❌ Check bekor qilindi!", show_alert=True)
        new_text = callback.message.text + f"\n❌ Bekor qilindi! {now}"
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=None  # Tugmalarni olib tashlash
        )

        from user import bot as userBot
        await userBot.send_message(user_id, (
            f"❌ Sizning so'rovingiz bekor qilindi!\n"
            f"📌 Tranzaksiya ID: {transaction_id}\n"
            f"💰 Hisobingizda {user_balance:,.0f} so'm\n"
        ))



@router.message(Command("transaction"))
async def handle_admin_transaction(message: types.Message, command: CommandObject, bot: Bot):
    admin_id = get_admin_id()
    if message.from_user.id != admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return
    
    if not command.args:
        return await message.answer("❗ Iltimos, tranzaksiya ID ni kiriting.\n\nMisol: `/transaction 123`")

    try:
        transaction_id = int(command.args)
    except ValueError:
        return await message.answer("🚨 Noto‘g‘ri ID! Tranzaksiya ID faqat raqam bo‘lishi kerak.")

    await admin_transaction_info(transaction_id)


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    admin_id = get_admin_id()

    if user_id == admin_id:
        await message.answer("✅ Siz admin sifatida tolovlarni qabul qilishingiz mumkun")
    else:
        await message.answer("⛔ Siz admin sifatida topilmadingiz!")


@router.message(Command("change_admin"))
async def change_admin_handler(message: types.Message):
    """Admin ID ni o'zgartirish komandasi"""
    admin_id = get_admin_id()
    if message.from_user.id != admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Foydalanish: /change_admin <yangi_admin_id>")
        return

    new_admin_id = int(args[1])
    update_admin_id(new_admin_id)
    
    await message.answer(f"✅ Admin ID {new_admin_id} ga o‘zgartirildi!")


@router.message(Command("change_card"))
async def change_card_start(message: types.Message, state: FSMContext):
    """Admin karta ma'lumotlarini o'zgartirishni boshlaydi"""
    admin_id = get_admin_id()
    if message.from_user.id != admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    await message.answer("💳 Yangi karta raqamini kiriting (masalan: 8600 1234 5678 9012):")
    await state.set_state(ChangeCardState.waiting_for_card_number)


@router.message(ChangeCardState.waiting_for_card_number)
async def process_card_number(message: types.Message, state: FSMContext):
    """Yangi karta raqamini olish"""
    new_card_number = message.text

    if len(new_card_number) != 19 or not new_card_number.replace(" ", "").isdigit():
        await message.answer("❌ Noto'g'ri format! Karta raqami 16 ta raqam va bo'shliqlar bilan bo‘lishi kerak.")
        return

    await state.update_data(card_number=new_card_number)
    await message.answer("👤 Karta egasining ismini kiriting (masalan: John Doe):")
    await state.set_state(ChangeCardState.waiting_for_card_holder)


@router.message(ChangeCardState.waiting_for_card_holder)
async def process_card_holder(message: types.Message, state: FSMContext):
    """Yangi karta egasining ismini olish"""
    new_card_holder = message.text

    data = await state.get_data()
    new_card_number = data["card_number"]

    update_card_details(new_card_number, new_card_holder)

    await message.answer(f"✅ Karta ma'lumotlari yangilandi!\n💳 {new_card_number}\n👤 {new_card_holder}")
    await state.clear()  # State-ni tugatish



async def start_admin_bot():
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    print(f"Admin {bot_username} bot ishga tushdi!")
    await set_commands()
    await dp.start_polling(bot)

