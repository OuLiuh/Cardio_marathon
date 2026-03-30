import re
import logging
import pytesseract
from PIL import Image
from abc import ABC, abstractmethod
from io import BytesIO
from schemas import WorkoutData

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseWorkoutParser(ABC):
    """
    Абстрактный класс для парсинга упражнений.
    Определяет общий интерфейс и базовые методы для всех парсеров.
    """

    def __init__(self, user_id: int, sport_type: str):
        """
        Инициализация парсера.

        :param user_id: ID пользователя для привязки данных.
        :param sport_type: Тип спорта (например, "бег", "велосипед").
        """
        self.user_id = user_id
        self.sport_type = sport_type

    def _preprocess_image(self, image_bytes: bytes) -> Image.Image:
        """
        Преобразует байты изображения в объект PIL и конвертирует в оттенки серого.

        :param image_bytes: Изображение в виде байтов.
        :return: Объект PIL.Image в градациях серого.
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            return image.convert('L')  # Чёрно-белое изображение улучшает OCR
        except Exception as e:
            raise ValueError(f"Не удалось загрузить изображение: {e}")

    @abstractmethod
    def parse_image(self, image_bytes: bytes) -> WorkoutData:
        """
        Абстрактный метод для парсинга изображения.
        Должен быть реализован в подклассах.

        :param image_bytes: Изображение в байтах.
        :return: Объект WorkoutData с распознанными данными.
        """
        pass


class UniversalParser(BaseWorkoutParser):
    """
    Универсальный парсер. Пытается найти знакомые паттерны (км, ккал, мин)
    с помощью регулярных выражений после OCR-распознавания текста.
    """

    def parse_image(self, image_bytes: bytes) -> WorkoutData:
        """
        Основной метод парсинга: принимает изображение, применяет OCR,
        извлекает данные о дистанции, времени и калориях.

        :param image_bytes: Изображение тренировки в байтах.
        :return: Объект WorkoutData с заполненными полями.
        """
        if not isinstance(image_bytes, bytes) or len(image_bytes) == 0:
            raise ValueError("image_bytes должен быть непустым объектом bytes")

        try:
            image = self._preprocess_image(image_bytes)
            raw_text = pytesseract.image_to_string(image, lang='rus+eng')
            logger.debug(f"Распознанный текст: {raw_text}")
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract не найден. Убедитесь, что он установлен и доступен в PATH."
            )
        except Exception as e:
            raise RuntimeError(f"Ошибка при обработке изображения: {e}")

        distance = self._find_distance(raw_text)
        duration = self._find_duration(raw_text)
        calories = self._find_calories(raw_text)

        return WorkoutData(
            user_id=self.user_id,
            sport_type=self.sport_type,
            distance_km=distance,
            duration_minutes=duration,
            calories=calories,
            avg_heart_rate=None  # Пока не поддерживается
        )

    def _find_distance(self, text: str) -> float:
        """
        Ищет в тексте значение дистанции с единицами измерения (km, км и др.).

        Поддерживает: km, км, километров, км., с десятичными точками и запятыми.
        Примеры: "5.2 km", "10,5 км".

        :param text: Текст, полученный из OCR.
        :return: Дистанция в километрах или 0.0, если не найдено.
        """
        match = re.search(
            r'(\d+(?:[.,]\d+)?)\s*(?:km|км|километр|километров|км\.)', text, re.IGNORECASE
        )
        if match:
            val_str = match.group(1).replace(',', '.')
            try:
                return float(val_str)
            except ValueError:
                return 0.0
        return 0.0

    def _find_duration(self, text: str) -> int:
        """
        Ищет в тексте продолжительность в форматах:
        - ЧЧ:ММ:СС (например, 01:30:45)
        - ММ:СС (например, 45:30 — 45 минут 30 секунд)

        :param text: Текст, полученный из OCR.
        :return: Общее время в минутах или 0, если не найдено.
        """
        # Формат ЧЧ:ММ:СС
        time_match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', text)
        if time_match:
            hours, minutes, seconds = map(int, time_match.groups())
            return hours * 60 + minutes

        # Формат ММ:СС (до 599 минут)
        time_match = re.search(r'(\d{1,3}):(\d{2})\b', text)
        if time_match:
            minutes, seconds = map(int, time_match.groups())
            if minutes < 600:  # Разумное ограничение
                return minutes + (1 if seconds >= 30 else 0)  # Округление по секундам

        return 0

    def _find_calories(self, text: str) -> int:
        """
        Ищет в тексте значение калорий с различными обозначениями:
        kcal, cal, ккал, Калории.

        Примеры: "320 kcal", "500 ккал".

        :param text: Текст, полученный из OCR.
        :return: Количество калорий или 0, если не найдено.
        """
        match = re.search(
            r'(\d+)\s*(?:kcal|cal|ккал|Калории|калорий)', text, re.IGNORECASE
        )
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return 0
        return 0