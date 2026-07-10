# Карта проекта Cardio_marathon

## Общая архитектура

Standalone веб-приложение: FastAPI + React/Vite + PostgreSQL, оркестрация через Docker Compose.

---

## Корень проекта

- **`.github/`** — GitHub Actions (деплой на VPS).
- **`.gitignore`** — исключения из git (`.venv/`, `__pycache__`, `.env`).
- **`docker-compose.yml`** — сервисы: `db`, `backend`, `frontend`, `nginx`.
- **`backend/`** — FastAPI: API, игровые механики, OCR, JWT-auth.
- **`frontend/`** — React + Vite: UI игры.
- **`nginx/`** — HTTPS и проксирование.

---

## backend/

- **`main.py`** — точка входа FastAPI.
- **`config.py`** — переменные окружения.
- **`database.py`** — SQLAlchemy async engine/session.
- **`models.py`** — ORM-модели.
- **`schemas.py`** — Pydantic-схемы.
- **`auth.py`** — bcrypt + JWT.
- **`ocr_service.py`** — OCR через OpenRouter.
- **`mechanics.py`** — расчёт урона.
- **`boss_factory.py`** — генерация боссов.
- **`shop_config.py`** — магазин улучшений.
- **`requirements.txt`** / **`Dockerfile`**

---

## frontend/

- **`src/`** — React-приложение.
- **`index.html`** — точка входа.
- **`package.json`** / **`vite.config.js`**
- **`nginx.conf`** / **`Dockerfile`**

---

## nginx/

- **`default.conf`** — `/api/*` → backend, `/` → frontend, SSL.
