FROM python:3.12-slim

# Установка Python-зависимостей.
# Слой отделён от копирования кода, чтобы кэш Docker не инвалидировался
# при каждом изменении исходников — pip install выполняется только при
# изменении requirements.txt.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения.
# Используется .dockerignore, чтобы не тащить в образ .venv, __pycache__ и т.п.
COPY . .

# Запуск сервера.
# --proxy-headers / --forwarded-allow-ips — корректное определение
# реального IP клиента за nginx.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
