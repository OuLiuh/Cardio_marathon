import re
import logging
import pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from abc import ABC, abstractmethod
from io import BytesIO
from schemas import WorkoutData

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

    def _preprocess_image(self, image_bytes: bytes) -> Image.Image:
        """
        Улучшенная предобработка изображения для OCR.
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Конвертируем в градации серого
            image = image.convert('L')
            
            # Увеличиваем размер для лучшего распознавания
            image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
            
            # Увеличиваем контрастность
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Увеличиваем яркость
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.2)
            
            # Применяем резкость
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            # Бинаризация (черно-белое)
            image = image.point(lambda x: 0 if x < 128 else 255, mode='1')
            
            return image
        except Exception as e:
            raise ValueError(f"Не удалось загрузить изображение: {e}")

    @abstractmethod
    def parse_image(self, image_bytes: bytes) -> WorkoutData:
        pass


class UniversalParser(BaseWorkoutParser):
    """
    Универсальный парсер с улучшенным поиском метрик.
    """

    def parse_image(self, image_bytes: bytes) -> WorkoutData:
        if not isinstance(image_bytes, bytes) or len(image_bytes) == 0:
            raise ValueError("image_bytes должен быть непустым объектом bytes")

        raw_text = ""
        try:
            image = self._preprocess_image(image_bytes)
            
            # Распознавание с разными конфигурациями для лучшего результата
            raw_text = pytesseract.image_to_string(image, lang='rus+eng', config='--psm 6 --oem 1')
            
            # Дополнительная попытка с другим режимом
            raw_text_alt = pytesseract.image_to_string(image, lang='rus+eng', config='--psm 11 --oem 1')
            
            # Объединяем результаты
            raw_text = raw_text + "\n" + raw_text_alt
            
            logger.info(f"Распознанный текст для user {self.user_id}: {raw_text}")
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract не найден. Установите tesseract-ocr.")
            raw_text = "ERROR: Tesseract not found"
        except Exception as e:
            logger.error(f"OCR ошибка: {e}", exc_info=True)
            raw_text = f"ERROR: {str(e)}"

        # Поиск метрик
        distance = self._find_distance(raw_text)
        duration = self._find_duration(raw_text)
        calories = self._find_calories(raw_text)

        logger.info(f"Распознанные метрики: distance={distance}km, duration={duration}min, calories={calories}kcal")

        return WorkoutData(
            user_id=self.user_id,
            sport_type=self.sport_type,  # Используем указанный пользователем тип
            distance_km=distance,
            duration_minutes=duration,
            calories=calories,
            avg_heart_rate=0,
            raw_text=raw_text if raw_text else "Текст не распознан"
        )

    def _find_distance(self, text: str) -> float:
        """
        Ищет дистанцию с поддержкой различных форматов.
        """
        text = text.lower().replace(',', '.').replace(' ', '')
        
        # Паттерны: 5.2km, 10.5км, 3километра, 7.км
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:km|км|километр[аов]?)',
            r'(\d+(?:\.\d+)?)\s*k',
            r'дистанция[:\s]*(\d+(?:\.\d+)?)',
            r'distance[:\s]*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return 0.0

    def _find_duration(self, text: str) -> int:
        """
        Ищет продолжительность в различных форматах.
        """
        text_lower = text.lower()
        
        # Формат ЧЧ:ММ:СС
        time_match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', text)
        if time_match:
            hours, minutes, seconds = map(int, time_match.groups())
            return hours * 60 + minutes + (1 if seconds >= 30 else 0)

        # Формат ММ:СС
        time_match = re.search(r'(\d{1,3}):(\d{2})\b', text)
        if time_match:
            minutes, seconds = map(int, time_match.groups())
            if minutes < 600:
                return minutes + (1 if seconds >= 30 else 0)

        # Поиск по ключевым словам: время, duration, time
        duration_match = re.search(r'(?:время|duration|time)[:\s]*(\d+)\s*(?:мин|min|м)?', text_lower)
        if duration_match:
            return int(duration_match.group(1))

        return 0

    def _find_calories(self, text: str) -> int:
        """
        Ищет калории с поддержкой различных обозначений.
        """
        text_lower = text.lower().replace(',', '').replace(' ', '')
        
        patterns = [
            r'(\d+)\s*(?:kcal|ккал|калорий|калории|cal)',
            r'(?:калории|калорий|calories)[:\s]*(\d+)',
            r'(\d+)\s*ккал',
            r'энергия[:\s]*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return 0