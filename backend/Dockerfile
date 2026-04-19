FROM python:3.10-slim

# Установка Tesseract OCR — необходим для pytesseract
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-rus \
        libtesseract-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Запуск сервера
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]