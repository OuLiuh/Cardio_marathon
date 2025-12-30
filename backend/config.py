import os
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent.parent
dotenv_path = base_dir / '.env'

if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Присваиваем переменные константам
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_DB', "db") # Название контейнера в docker
POSTGRES_PORT = os.getenv('POSTGRES_DB', "5432") # 5432 по умолчанию

DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL')

# Проверка на обязательные переменные
if not POSTGRES_USER:
    raise ValueError("В файле .env не задан POSTGRES_USER!")
if not POSTGRES_PASSWORD:
    raise ValueError("В файле .env не задан POSTGRES_PASSWORD!")
if not POSTGRES_DB:
    raise ValueError("В файле .env не задан POSTGRES_DB!")
if not POSTGRES_HOST:
    raise ValueError("В файле .env не задан POSTGRES_HOST!")
if not POSTGRES_PORT:
    raise ValueError("В файле .env не задан POSTGRES_PORT!")
if not DATABASE_URL:
    raise ValueError("В файле .env не задан DATABASE_URL!")
if not BOT_TOKEN:
    raise ValueError("В файле .env не задан BOT_TOKEN!")
if not WEBAPP_URL:
    raise ValueError("В файле .env не задан WEBAPP_URL!")