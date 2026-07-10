# Cardio Marathon (Pulse Guardian) — обзор проекта

## Кратко

Геймифицированный кардио-марафон: игроки загружают скриншоты тренировок, система распознаёт метрики (OCR через LLM), считает урон по боссу в общем рейде и начисляет XP/золото. Клиент — Telegram Mini App (WebApp).

---

## Стек технологий

### Бэкенд
| Технология | Назначение |
|---|---|
| **Python 3.12** | Язык сервиса |
| **FastAPI** | REST API |
| **Uvicorn** | ASGI-сервер |
| **SQLAlchemy 2.x (async)** + **asyncpg** | ORM и драйвер PostgreSQL |
| **Pydantic 2** | Валидация запросов/ответов |
| **PostgreSQL 15** | Основная БД |
| **bcrypt** + **PyJWT** | Хеширование паролей и JWT (`auth.py`; в текущем `main.py` эндпоинты auth могут быть не подключены) |
| **httpx** | HTTP-клиент к OpenRouter (OCR) |
| **python-multipart** | Загрузка файлов (фото тренировок) |
| **python-dotenv** | Переменные из `.env` |

### Фронтенд
| Технология | Назначение |
|---|---|
| **React 19** | UI |
| **Vite 7** | Сборка и dev-сервер |
| **ESLint** | Линтинг |
| **Telegram WebApp API** | Авторизация/контекст пользователя в Mini App |
| **Nginx (alpine)** | Раздача статики после `vite build` |

Маршрутизатора (React Router) нет — экраны переключаются через `useState` в одном компоненте `App.jsx`.

### Telegram-бот
| Технология | Назначение |
|---|---|
| **aiogram 3.10** | Бот с командой `/start` и кнопкой открытия WebApp |

### Инфраструктура
| Компонент | Назначение |
|---|---|
| **Docker Compose** | Оркестрация: `db`, `backend`, `frontend`, `bot`, `nginx` |
| **Nginx (корневой)** | HTTPS, прокси `/api` → backend, `/` → frontend |
| **GitHub Actions** | Деплой на VPS по push в `main` |

---

## Архитектура (сервисы)

```
Telegram → Bot (кнопка WebApp)
                ↓
Пользователь → Nginx (:80/:443)
                 ├─ /api/*  → Backend (FastAPI :8000)
                 │              └─ PostgreSQL
                 │              └─ OpenRouter (OCR)
                 └─ /*      → Frontend (Nginx + React static)
```

---

## Содержимое файлов и каталогов

### Корень проекта

| Путь | Содержание |
|---|---|
| `docker-compose.yml` | Сервисы: Postgres, backend, frontend, bot, nginx; volume `postgres_data` |
| `.gitignore` | Исключения из git (venv, env, кэши и т.п.) |
| `.github/workflows/deploy.yml` | CI/CD: SSH на VPS → `git pull` → `docker compose up -d --build` |
| `structure_map.md` | Краткая карта структуры (ранний обзор) |
| `backend/architecture_review.md` | Архитектурный разбор бэкенда (паттерны, риски, рекомендации) |
| `PROJECT_OVERVIEW.md` | Этот документ |
| `.env` (не в репо) | Секреты: Postgres, `SECRET_KEY`, `BOT_TOKEN`, `WEBAPP_URL`, `OPENROUTER_API_KEY` |
| `certs/` (не в репо / локально) | SSL-сертификаты для nginx |

---

### `backend/` — API и игровая логика

| Файл | Содержание |
|---|---|
| `main.py` | Точка входа FastAPI; эндпоинты атаки, рейда, пользователя, магазина, OCR |
| `config.py` | Загрузка `.env`, `DATABASE_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY` |
| `database.py` | Async engine/session SQLAlchemy, `init_models()`, `get_db()` |
| `models.py` | ORM: `User`, `UserUpgrade`, `Raid`, `RaidLog` |
| `schemas.py` | Pydantic-схемы API (`WorkoutData`, `RaidState`, магазин и т.д.) |
| `mechanics.py` | Стратегии урона: бег, вело, плавание, футбол; учёт апгрейдов и трейтов босса |
| `boss_factory.py` | Генерация боссов (HP, traits, имя) по числу игроков |
| `shop_config.py` | Реестр улучшений магазина и их эффекты |
| `ocr_service.py` | `UniversalParser`: фото → base64 → OpenRouter LLM → `WorkoutData` |
| `auth.py` | bcrypt + JWT (модуль готов; интеграция в роуты — отдельно) |
| `requirements.txt` | Python-зависимости бэкенда |
| `Dockerfile` | Образ Python 3.12 + uvicorn |
| `.dockerignore` | Исключения при сборке образа |

#### API-эндпоинты (`main.py`)

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/attack` | Атака босса по данным тренировки |
| `GET` | `/api/raid/current` | Текущее состояние рейда |
| `GET` | `/api/raid/state` | Альтернативный/базовый путь состояния рейда |
| `GET` | `/api/user/{user_id}` | Профиль пользователя |
| `POST` | `/api/user/register` | Регистрация (Telegram id + username) |
| `GET` | `/api/shop/{user_id}` | Список товаров магазина |
| `POST` | `/api/shop/buy` | Покупка улучшения |
| `POST` | `/api/scan-workout` | OCR скриншота тренировки |

#### Модели БД

- **User** — id (Telegram), username, password_hash, level, xp, gold  
- **UserUpgrade** — уровни купленных улучшений  
- **Raid** — босс, HP, debuffs, traits, активность  
- **RaidLog** — лог атак (урон, спорт, crit/miss, награды)

---

### `frontend/` — Telegram Mini App (React)

| Путь | Содержание |
|---|---|
| `index.html` | HTML-оболочка, точка монтирования |
| `src/main.jsx` | Bootstrap React (`createRoot`) |
| `src/App.jsx` | Весь UI: экраны loading / rules / welcome / main / shop; OCR-форма; атака |
| `src/api.js` | Клиент к бэкенду (`fetch` / XHR для OCR) |
| `src/App.css`, `src/index.css` | Стили |
| `package.json` | Зависимости: React 19, Vite 7, ESLint |
| `vite.config.js` | Конфиг Vite + `@vitejs/plugin-react` |
| `eslint.config.js` | Правила ESLint |
| `nginx.conf` | Nginx внутри контейнера фронтенда (SPA) |
| `Dockerfile` | Multi-stage: `npm build` → nginx:alpine |
| `README.md` | Шаблонный README Vite |

Экраны в `App.jsx`: загрузка → правила → приветствие → арена рейда → магазин. Данные пользователя берутся из Telegram WebApp.

---

### `bot/` — Telegram-бот

| Файл | Содержание |
|---|---|
| `bot.py` | `/start` + inline-кнопка WebApp (`WEBAPP_URL`) |
| `requirements.txt` | `aiogram==3.10.0` |
| `Dockerfile` | Образ бота |
| `.dockerignore` | Исключения сборки |

---

### `nginx/` — внешний reverse proxy

| Файл | Содержание |
|---|---|
| `default.conf` | HTTP→HTTPS, SSL, `client_max_body_size 20M`, прокси `/api/` и `/` |

Домен в конфиге задан в punycode (кириллический домен).

---

## Игровой цикл (логика продукта)

1. Пользователь открывает Mini App через бота.  
2. Регистрация по Telegram `id` + имени.  
3. Загрузка скриншота тренировки → `/api/scan-workout` (OCR).  
4. Подтверждение/правка метрик → `/api/attack`.  
5. Стратегия по виду спорта считает урон с учётом уровня и апгрейдов.  
6. Урон списывается с HP босса; пишутся лог, XP, золото.  
7. При отсутствии активного рейда `BossFactory` создаёт нового босса.  
8. Золото тратится в магазине на улучшения (`shop_config`).

Поддерживаемые виды спорта в схемах/механиках: **run**, **cycle**, **swim**, **football**.

---

## Запуск (локально / прод)

1. Создать `.env` с переменными Postgres, `SECRET_KEY`, `BOT_TOKEN`, `WEBAPP_URL`, `OPENROUTER_API_KEY`.  
2. Положить SSL-сертификаты в `certs/` (для HTTPS через корневой nginx).  
3. Запуск:

```bash
docker compose up -d --build
```

- Backend: порт `8000` (также через nginx `/api`)  
- Frontend: через nginx на `80`/`443`  
- БД: только внутри Docker-сети (без публикации наружу)

---

## Связанные документы в репозитории

- `structure_map.md` — краткая карта каталогов  
- `backend/architecture_review.md` — оценка архитектуры бэкенда (Strategy/Factory, риски, рефакторинг)
