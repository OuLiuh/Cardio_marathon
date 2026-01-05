# backend/shop_config.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from schemas import WorkoutData

# Базовый класс апгрейда
class BaseUpgrade(ABC):
    def __init__(self, key: str, name: str, description: str, sport_type: str, max_level: int = 10, base_price: int = 100):
        self.key = key
        self.name = name
        self.description = description
        self.sport_type = sport_type
        self.max_level = max_level
        self.base_price = base_price

    def get_price(self, current_level: int) -> int:
        # Цена растет с каждым уровнем
        if current_level >= self.max_level:
            return 999999
        return self.base_price * (current_level + 1)
        
    def is_locked(self, user_upgrades: Dict[str, int]) -> bool:
        return False

    # Хук 1: Модификация входных данных (дистанция, время)
    def modify_input(self, level: int, data: WorkoutData):
        pass
        
    # Хук 2: Модификация итогового урона
    def modify_damage(self, level: int, damage: float) -> float:
        return damage

# --- Конкретные реализации ---

class DurationUpgrade(BaseUpgrade):
    def __init__(self, key, name, desc, sport, minutes_per_level):
        super().__init__(key, name, desc, sport)
        self.minutes_per_level = minutes_per_level
        
    def modify_input(self, level: int, data: WorkoutData):
        if data.sport_type == self.sport_type and data.duration_minutes is not None:
            data.duration_minutes += (level * self.minutes_per_level)

class DistanceUpgrade(BaseUpgrade):
    def __init__(self, key, name, desc, sport, km_per_level):
        super().__init__(key, name, desc, sport)
        self.km_per_level = km_per_level
        
    def modify_input(self, level: int, data: WorkoutData):
        if data.sport_type == self.sport_type and data.distance_km is not None:
            data.distance_km += (level * self.km_per_level)

class CaloriesUpgrade(BaseUpgrade):
    def __init__(self, key, name, desc, sport, kcal_per_level):
        super().__init__(key, name, desc, sport)
        self.kcal_per_level = kcal_per_level
        
    def modify_input(self, level: int, data: WorkoutData):
        if data.sport_type == self.sport_type and data.calories is not None:
            data.calories += (level * self.kcal_per_level)

class SuperUpgrade(BaseUpgrade):
    """Супер-апгрейд: x2 урон. Доступен только если куплены все остальные апгрейды этого спорта на макс."""
    def __init__(self, key, name, desc, sport, required_keys: List[str]):
        super().__init__(key, name, desc, sport, max_level=1, base_price=2000)
        self.required_keys = required_keys
        
    def is_locked(self, user_upgrades: Dict[str, int]) -> bool:
        # Проверяем, что все пререквизиты 10 уровня
        for req_key in self.required_keys:
            if user_upgrades.get(req_key, 0) < 10:
                return True
        return False
        
    def modify_damage(self, level: int, damage: float) -> float:
        if level > 0 and damage > 0:
            return damage * 2.0
        return damage

# --- Реестр Магазина ---

SHOP_ITEMS: List[BaseUpgrade] = [
    # Бег
    DurationUpgrade("run_watch", "Бегущие часы", "+1 мин/ур к времени", "run", 1),
    DistanceUpgrade("run_roulette", "Накрученная рулетка", "+200м/ур к дистанции", "run", 0.2),
    SuperUpgrade("run_super", "Титановый Кроссовок", "x2 УРОН (Нужно: Часы 10 + Рулетка 10)", "run", ["run_watch", "run_roulette"]),
    
    # Вело
    DurationUpgrade("cycle_watch", "Вело-компьютер", "+2 мин/ур к времени", "cycle", 2),
    DistanceUpgrade("cycle_odometer", "Сломанный одометр", "+1км/ур к дистанции", "cycle", 1.0),
    SuperUpgrade("cycle_super", "Карбоновая Рама", "x2 УРОН (Нужно: Комп 10 + Одометр 10)", "cycle", ["cycle_watch", "cycle_odometer"]),
    
    # Плавание
    DistanceUpgrade("swim_flippers", "Ласты", "+100м/ур к дистанции", "swim", 0.1),
    SuperUpgrade("swim_super", "Жабры", "x2 УРОН (Нужно: Ласты 10)", "swim", ["swim_flippers"]),
    
    # Футбол
    CaloriesUpgrade("football_energy", "Энергетик", "+100 ккал/ур", "football", 100),
    SuperUpgrade("football_super", "Золотой Мяч", "x2 УРОН (Нужно: Энергетик 10)", "football", ["football_energy"])
]

SHOP_REGISTRY = {item.key: item for item in SHOP_ITEMS}