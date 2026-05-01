import re
import logging
import base64
import json
import httpx
from abc import ABC, abstractmethod
from typing import Optional
from schemas import WorkoutData
from config import OPENROUTER_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseWorkoutParser(ABC):
    """
    Абстрактный класс для парсинга упражнений.
    """

    def __init__(self, user_id: int, sport_type: str):
        self.user_id = user_id
        self.sport_type = sport_type

    @abstractmethod
    async def parse_image(self, image_bytes: bytes) -> WorkoutData:
        pass

class UniversalParser(BaseWorkoutParser):
    """
    Парсер с использованием LLM (OpenRouter) для распознавания метрик.
    """

    async def parse_image(self, image_bytes: bytes) -> WorkoutData:
        if not isinstance(image_bytes, bytes) or len(image_bytes) == 0:
            raise ValueError("image_bytes должен быть непустым объектом bytes")

        if not OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY не установлен!")
            raise ValueError("Отсутствует ключ API для OpenRouter")

        # Кодируем изображение в base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Формируем промпт в зависимости от вида спорта
        if self.sport_type == "run":
            sport_name = "бега"
            metrics_req = "1. Дистанция (в километрах)\n2. Время (в минутах)\n3. Калории (в ккал)"
        elif self.sport_type == "cycle":
            sport_name = "велосипеда"
            metrics_req = "1. Дистанция (в километрах)\n2. Время (в минутах)"
        elif self.sport_type == "swim":
            sport_name = "плавания"
            metrics_req = "1. Дистанция (в километрах)\n2. Время (в минутах)"
        elif self.sport_type == "football":
            sport_name = "футбола"
            metrics_req = "1. Время (в минутах)\n2. Калории (в ккал)"
        else:
            sport_name = "тренировки"
            metrics_req = "1. Дистанция (в километрах)\n2. Время (в минутах)\n3. Калории (в ккал)"

        prompt = f"""
Проанализируй этот скриншот {sport_name}.
Найди следующие данные:
{metrics_req}

ВАЖНЫЕ ПРАВИЛА ОКРУГЛЕНИЯ:
- Время округляй в МЕНЬШУЮ сторону до целых минут (например, 31:45 или 31 мин 45 сек -> 31).
- Дистанцию округляй в МЕНЬШУЮ сторону до десятых долей километра (например, 5.29 -> 5.2).

Верни результат СТРОГО в таком формате (без лишних слов и символов):
Дистанция <число> км
Время <число> мин
Каллории <число>

Если какой-то метрики нет в списке выше или она не найдена на фото, напиши 0.
"""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://cardiomarathon.com", # Замените на ваш URL
            "X-Title": "Cardio Marathon"
        }

        payload = {
            "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", # Можно заменить на google/gemini-2.5-flash
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1
        }

        raw_text = "Текст не распознан"
        distance = 0.0
        duration = 0
        calories = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    raw_text = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"Ответ OpenRouter для user {self.user_id}: \n{raw_text}")
                    
                    # Парсим ответ
                    distance = self._parse_distance(raw_text)
                    duration = self._parse_duration(raw_text)
                    calories = self._parse_calories(raw_text)
                else:
                    logger.error(f"Неожиданный ответ от OpenRouter: {result}")
                    raw_text = f"Ошибка API: {result}"

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка при обращении к OpenRouter: {e.response.text}")
            raw_text = f"HTTP ошибка API: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Ошибка при обращении к OpenRouter: {e}", exc_info=True)
            raw_text = f"Ошибка: {str(e)}"

        logger.info(f"Распознанные метрики: distance={distance}km, duration={duration}min, calories={calories}kcal")

        return WorkoutData(
            user_id=self.user_id,
            sport_type=self.sport_type,
            distance_km=distance,
            duration_minutes=duration,
            calories=calories,
            avg_heart_rate=0,
            raw_text=raw_text
        )

    def _parse_distance(self, text: str) -> float:
        match = re.search(r'Дистанция\s+([\d.,]+)\s*км', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                pass
        return 0.0

    def _parse_duration(self, text: str) -> int:
        match = re.search(r'Время\s+(\d+)\s*мин', text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return 0

    def _parse_calories(self, text: str) -> int:
        match = re.search(r'Каллории\s+(\d+)', text, re.IGNORECASE)
        if not match:
            # На случай если нейросеть напишет с одной "л"
            match = re.search(r'Калории\s+(\d+)', text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return 0
