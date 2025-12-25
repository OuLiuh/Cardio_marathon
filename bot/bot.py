import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import WebAppInfo

# Берем токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
# Адрес твоего сайта (пока IP)
WEBAPP_URL = os.getenv("WEBAPP_URL") 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎮 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("Привет! Нажми кнопку, чтобы запустить игру.", reply_markup=markup)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())