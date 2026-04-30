import re
import logging
import pytesseract
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageStat
from abc import ABC, abstractmethod
from io import BytesIO
from typing import List
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
            
            # Определяем, темная ли тема (если средняя яркость меньше 127)
            # Tesseract значительно лучше работает с черным текстом на белом фоне
            stat = ImageStat.Stat(image)
            if stat.mean[0] < 127:
                image = ImageOps.invert(image)
            
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

        ocr_chunks: List[str] = []
        processed_image = None

        # 1) Предобработка
        try:
            processed_image = self._preprocess_image(image_bytes)
        except Exception as e:
            logger.error(f"Ошибка предобработки OCR: {e}", exc_info=True)
            ocr_chunks.append(f"ERROR: preprocess failed: {str(e)}")

        # 2) OCR в одном режиме для ускорения (psm 11 показал лучшие результаты)
        if processed_image is not None:
            try:
                text = pytesseract.image_to_string(processed_image, lang='rus+eng', config='--psm 11 --oem 1')
                if text and text.strip():
                    ocr_chunks.append(f"[psm11]\n{text.strip()}")
                else:
                    ocr_chunks.append("[psm11]\n(пустой результат)")
            except pytesseract.TesseractNotFoundError:
                logger.error("Tesseract не найден. Установите tesseract-ocr.")
                ocr_chunks.append("ERROR: Tesseract not found")
            except Exception as e:
                logger.error(f"OCR ошибка: {e}", exc_info=True)
                ocr_chunks.append(f"ERROR: {str(e)}")

        raw_text = "\n\n".join(ocr_chunks).strip() or "Текст не распознан"
        logger.info(f"Распознанный текст для user {self.user_id}: {raw_text}")

        # Поиск метрик по всему объединённому тексту
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
            raw_text=raw_text
        )

    def _find_distance(self, text: str) -> float:
        """
        Ищет дистанцию с поддержкой различных форматов.
        """
        text_lower = text.lower()
        text_dot = text_lower.replace(',', '.')
        
        # 1. Поиск явных указаний с "км" или "km" (с учетом возможных пробелов внутри числа)
        # Например: "5 . 22 км" или "5 22 km"
        match = re.search(r'(\d{1,2})[\s.]+(\d{1,2})\s*(?:km|км|k|к)\b', text_dot)
        if match:
            return float(f"{match.group(1)}.{match.group(2)}")
            
        # Стандартные "5.22 км"
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:km|км|k|к)\b', text_dot)
        if match:
            return float(match.group(1))
            
        # 2. Поиск по ключевым словам
        match = re.search(r'(?:дистанция|distance)[:\s]*(\d+(?:\.\d+)?)', text_dot)
        if match:
            return float(match.group(1))
            
        # 3. Специфичный паттерн для Mi Fitness (psm11), где км обрезается в "..."
        # Например: "5,22..." -> "5.22"
        match = re.search(r'(\d+\.\d{1,2})\.{2,}', text_dot)
        if match:
            return float(match.group(1))
            
        # 4. Поиск числа с плавающей точкой на отдельной строке (часто это самое крупное число - дистанция)
        # Ищем строку, где только цифры и точка/запятая
        match = re.search(r'(?m)^\s*(\d+\.\d{1,2})\s*$', text_dot)
        if match:
            return float(match.group(1))

        # 5. Fallback: удаляем все пробелы и ищем снова
        text_clean = text_dot.replace(' ', '').replace('\n', '')
        patterns = [
            r'(\d+(?:\.\d+)?)(?:km|км|километр[аов]?)',
            r'(\d+(?:\.\d+)?)k',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_clean)
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
        
        # Формат ЧЧ:ММ:СС или ЧЧ.ММ.СС
        time_match = re.search(r'(\d{1,2})[:.](\d{2})[:.](\d{2})', text)
        if time_match:
            hours, minutes, seconds = map(int, time_match.groups())
            return hours * 60 + minutes + (1 if seconds >= 30 else 0)

        # Формат ММ:СС или ММ.СС
        time_match = re.search(r'(\d{1,3})[:.](\d{2})\b', text)
        if time_match:
            minutes, seconds = map(int, time_match.groups())
            if minutes < 600:
                return minutes + (1 if seconds >= 30 else 0)

        # Поиск по ключевым словам: время, duration, time, длительность
        duration_match = re.search(r'(?:время|duration|time|длительность)[^\d]*(\d+)\s*(?:мин|min|м)?', text_lower)
        if duration_match:
            return int(duration_match.group(1))

        return 0

    def _find_calories(self, text: str) -> int:
        """
        Ищет калории с поддержкой различных обозначений.
        """
        text_clean = text.lower().replace(',', '').replace(' ', '').replace('\n', '')
        
        patterns = [
            r'(\d+)(?:kcal|ккал|калорий|калории|cal)',
            r'(?:калории|калорий|calories|активныеккал|всегоккал)[^\d]*(\d+)',
            r'энергия[^\d]*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return 0