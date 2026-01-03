# backend/mechanics.py
from abc import ABC, abstractmethod
import random
from schemas import WorkoutData

class DamageCalculationResult:
    def __init__(self, damage: int, is_crit: bool = False, is_miss: bool = False, applied_debuffs: dict = None):
        self.damage = int(damage)
        self.is_crit = is_crit
        self.is_miss = is_miss # Новый флаг: промах
        self.applied_debuffs = applied_debuffs or {}

class BaseWorkoutStrategy(ABC):
    def __init__(self, data: WorkoutData, user_level: int, raid_debuffs: dict, boss_traits: dict):
        self.data = data
        self.level = user_level
        self.raid_debuffs = raid_debuffs
        self.boss_traits = boss_traits # Характеристики босса

    def calculate(self) -> DamageCalculationResult:
        # 0. Проверка на Уворот (Agile Boss)
        evasion_chance = self.boss_traits.get("evasion_chance", 0)
        if evasion_chance > 0:
            # Если босс ловкий, кидаем кубик (0-100)
            if random.randint(1, 100) <= evasion_chance:
                # УВОРОТ! Урон 0
                return DamageCalculationResult(0, is_crit=False, is_miss=True, applied_debuffs={})

        # 1. Базовый расчет (Ккал)
        base_damage = self.data.calories
        
        # 2. Множитель уровня игрока
        level_multiplier = 1 + (self.level * 0.01) 
        
        # 3. Расчет специфики спорта
        damage, is_crit, new_debuffs = self._specific_calculation(base_damage)
        
        # 4. Учет брони (Armored Boss)
        # Если есть трейт armor_reduction И нет дебаффа armor_break
        armor_reduction = self.boss_traits.get("armor_reduction", 0)
        is_armor_broken = self.raid_debuffs.get("armor_break", False)
        
        # Если босс бронированный и броня НЕ пробита -> режем урон
        if armor_reduction > 0 and not is_armor_broken:
             damage *= (1.0 - armor_reduction)

        # 5. Бонус синергии (если броня пробита, все бьют чуть сильнее, даже если босс не был бронированным изначально)
        if is_armor_broken:
             damage *= 1.15

        final_damage = damage * level_multiplier
        
        return DamageCalculationResult(final_damage, is_crit, False, new_debuffs)

    @abstractmethod
    def _specific_calculation(self, base_damage: float):
        pass

# --- Реализации остаются почти такими же, Swimming важен для брони ---

class RunningStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self, base_damage: float):
        if self.data.duration_minutes < 30:
            return base_damage * 0.5, False, {}
        multiplier = 1 + (self.data.distance_km / 10.0)
        return base_damage * multiplier, False, {}

class CyclingStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self, base_damage: float):
        if self.data.duration_minutes < 30:
            return base_damage * 0.5, False, {}
        dmg = base_damage * 0.8
        if self.data.avg_heart_rate and self.data.avg_heart_rate > 130:
            dmg *= 1.05
        return dmg, False, {}

class SwimmingStrategy(BaseWorkoutStrategy):
    """Плавание ломает броню"""
    def _specific_calculation(self, base_damage: float):
        meters = self.data.distance_km * 1000
        dmg = (base_damage * 1.2) + (meters / 2)
        # Плаванье всегда пытается наложить armor_break
        return dmg, False, {"armor_break": True}

class FootballStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self, base_damage: float):
        is_crit = False
        dmg = base_damage
        crit_chance = 10
        if self.data.duration_minutes > 90:
            crit_chance = 50
        if random.randint(1, 100) <= crit_chance:
            is_crit = True
            dmg *= 2.5
        return dmg, is_crit, {}

def get_strategy(sport_type: str) -> type[BaseWorkoutStrategy]:
    strategies = {
        "run": RunningStrategy, "cycle": CyclingStrategy,
        "swim": SwimmingStrategy, "football": FootballStrategy
    }
    return strategies.get(sport_type, RunningStrategy)