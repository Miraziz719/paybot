import asyncio
import os
from admin import start_admin_bot
from user import start_user_bot
from db import init_db
from dotenv import load_dotenv
load_dotenv()


# 📂 Rasm saqlanadigan papka
RECEIPT_FOLDER = "receipts"
os.makedirs(RECEIPT_FOLDER, exist_ok=True) 

async def main():
    init_db()
    task1 = asyncio.create_task(start_admin_bot())  # Admin bot
    task2 = asyncio.create_task(start_user_bot())  # Oddiy foydalanuvchi bot

    await asyncio.gather(task1, task2)  # Ikkisini parallel ishlatish

if __name__ == "__main__":
    asyncio.run(main())
