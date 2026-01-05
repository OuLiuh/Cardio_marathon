# backend/mechanics.py
from abc import ABC, abstractmethod
import random
from schemas import WorkoutData
from shop_config import SHOP_REGISTRY

class DamageCalculationResult:
    def __init__(self, damage: int, is_crit: bool = False, is_miss: bool = False, applied_debuffs: dict = None):
        self.damage = int(damage)
        self.is_crit = is_crit
        self.is_miss = is_miss 
        self.applied_debuffs = applied_debuffs or {}

class BaseWorkoutStrategy(ABC):
    def __init__(self, data: WorkoutData, user_level: int, raid_debuffs: dict, boss_traits: dict, user_upgrades: dict):
        self.data = data
        self.level = user_level
        self.raid_debuffs = raid_debuffs
        self.boss_traits = boss_traits 
        self.user_upgrades = user_upgrades # Словарь {key: level}

    def calculate(self) -> DamageCalculationResult:
        # 0. ПРИМЕНЯЕМ АПГРЕЙДЫ К ВХОДНЫМ ДАННЫМ
        # Пробегаем по всем апгрейдам, которые есть у юзера, и даем им шанс изменить data
        for key, level in self.user_upgrades.items():
            if level > 0 and key in SHOP_REGISTRY:
                SHOP_REGISTRY[key].modify_input(level, self.data)

        # 0.1 Проверка на Уворот (после модификации данных, но до урона)
        evasion_chance = self.boss_traits.get("evasion_chance", 0)
        if evasion_chance > 0:
            if random.randint(1, 100) <= evasion_chance:
                return DamageCalculationResult(0, is_crit=False, is_miss=True, applied_debuffs={})

        # 1. Расчет базовой специфики
        damage, is_crit, new_debuffs = self._specific_calculation()
        
        # 2. Множитель уровня героя
        level_multiplier = 1 + (self.level * 0.01) 
        damage *= level_multiplier
        
        # 3. АПГРЕЙДЫ НА УРОН (Супер тренировки)
        for key, level in self.user_upgrades.items():
            if level > 0 and key in SHOP_REGISTRY:
                damage = SHOP_REGISTRY[key].modify_damage(level, damage)

        # 4. Учет брони босса
        armor_reduction = self.boss_traits.get("armor_reduction", 0)
        # Проверяем старые дебаффы ИЛИ новые, которые только что наложили
        is_armor_broken = self.raid_debuffs.get("armor_break", False) or new_debuffs.get("armor_break", False)
        
        if armor_reduction > 0 and not is_armor_broken:
             damage *= (1.0 - armor_reduction)

        # 5. Бонус пробитой брони
        if is_armor_broken:
             damage *= 1.15

        return DamageCalculationResult(damage, is_crit, False, new_debuffs)

    @abstractmethod
    def _specific_calculation(self):
        pass

class RunningStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        dist = self.data.distance_km
        time = self.data.duration_minutes
        
        # Урон - дистанция * 75 + время
        dmg = (dist * 75) + time
        if time < 30: dmg *= 0.8
        if dist > 5.0: dmg *= 1.1
            
        return dmg, False, {}

class CyclingStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        dist = self.data.distance_km
        time = self.data.duration_minutes
        
        # 30 очков за каждый км + время
        dmg = (30 * dist) + time
        return dmg, False, {}

class SwimmingStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        # метры/2
        meters = self.data.distance_km * 1000
        dmg = meters / 2
        
        debuffs = {}
        if random.randint(1, 100) <= 30: debuffs["armor_break"] = True
        return dmg, False, debuffs

class FootballStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        # калории/2
        calories = self.data.calories
        dmg = calories / 2
        debuffs = {}
        if random.randint(1, 100) <= 30: debuffs["armor_break"] = True
        return dmg, False, debuffs

def get_strategy(sport_type: str) -> type[BaseWorkoutStrategy]:
    strategies = {
        "run": RunningStrategy, "cycle": CyclingStrategy,
        "swim": SwimmingStrategy, "football": FootballStrategy
    }
    return strategies.get(sport_type, RunningStrategy)