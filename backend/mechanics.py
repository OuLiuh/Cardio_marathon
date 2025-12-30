# backend/mechanics.py
from abc import ABC, abstractmethod
import random
from schemas import WorkoutData

class DamageCalculationResult:
    def __init__(self, damage: int, is_crit: bool = False, applied_debuffs: dict = None):
        self.damage = int(damage)
        self.is_crit = is_crit
        self.applied_debuffs = applied_debuffs or {}

class BaseWorkoutStrategy(ABC):
    """Базовый класс для всех тренировок"""
    
    def __init__(self, data: WorkoutData, user_level: int, active_raid_debuffs: dict):
        self.data = data
        self.level = user_level
        self.raid_debuffs = active_raid_debuffs

    def calculate(self) -> DamageCalculationResult:
        # 1. Базовый расчет от калорий
        base_damage = self.data.calories
        
        # 2. Применение множителя уровня (каждые 10 уровней +10% силы, например)
        level_multiplier = 1 + (self.level * 0.01) 
        
        # 3. Специфичный расчет класса
        damage, is_crit, new_debuffs = self._specific_calculation(base_damage)
        
        # 4. Учет глобальных дебаффов босса (Синергия команды)
        # Если босс "Размок" (от плавания), урон увеличивается
        if self.raid_debuffs.get("armor_break") and self.data.sport_type != "swim":
            damage *= 1.15 # +15% урона всем остальным
            
        final_damage = damage * level_multiplier
        
        return DamageCalculationResult(final_damage, is_crit, new_debuffs)

    @abstractmethod
    def _specific_calculation(self, base_damage: float):
        pass

# --- Реализация классов ---

class RunningStrategy(BaseWorkoutStrategy):
    """Бег: Стабильный урон, бонус от дистанции"""
    def _specific_calculation(self, base_damage: float):
        if self.data.duration_minutes < 30:
            return base_damage * 0.5, False, {} # Штраф за короткую треню
            
        # Формула: Ккал * (1 + Дистанция/10)
        multiplier = 1 + (self.data.distance_km / 10.0)
        return base_damage * multiplier, False, {}

class CyclingStrategy(BaseWorkoutStrategy):
    """Вело: Много атак, сниженный базовый коэф"""
    def _specific_calculation(self, base_damage: float):
        if self.data.duration_minutes < 30:
            return base_damage * 0.5, False, {}

        # База 0.8, но пульс может баффнуть
        dmg = base_damage * 0.8
        
        # Если пульс высокий, огненные стрелы (+5% урона)
        if self.data.avg_heart_rate and self.data.avg_heart_rate > 130:
            dmg *= 1.05
            
        return dmg, False, {}

class SwimmingStrategy(BaseWorkoutStrategy):
    """Плавание: Пробитие брони (Armor Break)"""
    def _specific_calculation(self, base_damage: float):
        # Формула: (Ккал * 1.2) + (Метры / 2)
        # Дистанция приходит в км, переводим в метры
        meters = self.data.distance_km * 1000
        dmg = (base_damage * 1.2) + (meters / 2)
        
        # Накладываем дебафф на босса
        return dmg, False, {"armor_break": True}

class FootballStrategy(BaseWorkoutStrategy):
    """Футбол: Шанс крита"""
    def _specific_calculation(self, base_damage: float):
        is_crit = False
        dmg = base_damage
        
        # Шанс крита
        crit_chance = 10
        if self.data.duration_minutes > 90 and self.data.avg_heart_rate > 140:
            crit_chance = 50
            
        if random.randint(1, 100) <= crit_chance:
            is_crit = True
            dmg *= 2.5 # КРИТ!
            
        return dmg, is_crit, {}

# Фабрика для выбора стратегии
def get_strategy(sport_type: str) -> type[BaseWorkoutStrategy]:
    strategies = {
        "run": RunningStrategy,
        "cycle": CyclingStrategy,
        "swim": SwimmingStrategy,
        "football": FootballStrategy
    }
    return strategies.get(sport_type, RunningStrategy)