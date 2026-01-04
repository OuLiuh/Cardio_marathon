from abc import ABC, abstractmethod
import random
from schemas import WorkoutData

class DamageCalculationResult:
    def __init__(self, damage: int, is_crit: bool = False, is_miss: bool = False, applied_debuffs: dict = None):
        self.damage = int(damage)
        self.is_crit = is_crit
        self.is_miss = is_miss 
        self.applied_debuffs = applied_debuffs or {}

class BaseWorkoutStrategy(ABC):
    def __init__(self, data: WorkoutData, user_level: int, raid_debuffs: dict, boss_traits: dict):
        self.data = data
        self.level = user_level
        self.raid_debuffs = raid_debuffs
        self.boss_traits = boss_traits 

    def calculate(self) -> DamageCalculationResult:
        # 0. Проверка на Уворот
        evasion_chance = self.boss_traits.get("evasion_chance", 0)
        if evasion_chance > 0:
            if random.randint(1, 100) <= evasion_chance:
                return DamageCalculationResult(0, is_crit=False, is_miss=True, applied_debuffs={})

        # 1. Расчет специфики
        damage, is_crit, new_debuffs = self._specific_calculation()
        
        # 2. Множитель уровня
        level_multiplier = 1 + (self.level * 0.01) 
        
        # 3. Учет брони
        armor_reduction = self.boss_traits.get("armor_reduction", 0)
        # Проверяем старые дебаффы ИЛИ новые, которые только что наложили
        is_armor_broken = self.raid_debuffs.get("armor_break", False) or new_debuffs.get("armor_break", False)
        
        if armor_reduction > 0 and not is_armor_broken:
             damage *= (1.0 - armor_reduction)

        # 4. Бонус синергии (по пробитой броне все бьют сильнее)
        if is_armor_broken:
             damage *= 1.15

        final_damage = damage * level_multiplier
        
        return DamageCalculationResult(final_damage, is_crit, False, new_debuffs)

    @abstractmethod
    def _specific_calculation(self):
        pass

class RunningStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        dist = self.data.distance_km
        time = self.data.duration_minutes
        
        # Урон - дистанция * 75 + время
        dmg = (dist * 75) + time
        
        # Если меньше 30 минут, домножаем на 0.8
        if time < 30:
            dmg *= 0.8
        
        # Если больше 5 (5000м в км) то домножаем на 1.1
        if dist > 5.0:
            dmg *= 1.1
            
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
        # Вероятность снять броню 30%
        if random.randint(1, 100) <= 30:
            debuffs["armor_break"] = True
            
        return dmg, False, debuffs

class FootballStrategy(BaseWorkoutStrategy):
    def _specific_calculation(self):
        # калории/2
        calories = self.data.calories
        dmg = calories / 2
        
        debuffs = {}
        # Вероятность снять броню 30%
        if random.randint(1, 100) <= 30:
            debuffs["armor_break"] = True
            
        return dmg, False, debuffs

def get_strategy(sport_type: str) -> type[BaseWorkoutStrategy]:
    strategies = {
        "run": RunningStrategy, "cycle": CyclingStrategy,
        "swim": SwimmingStrategy, "football": FootballStrategy
    }
    return strategies.get(sport_type, RunningStrategy)