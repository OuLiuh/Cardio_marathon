# backend/boss_factory.py
import random
from models import Raid

class BossFactory:
    """
    Отвечает за генерацию параметров босса на основе статистики игроков.
    """
    
    PREFIXES = ["Titan", "Lord", "Giga", "Ancient", "Cyber"]
    NAMES = ["Sloth", "Gluttony", "Entropy", "Static", "Couch Potato"]
    
    @staticmethod
    def calculate_hp(active_players: int) -> int:
        """
        Формула: (Игроки * 3 тренировки * 350 ср.урон) * 1.2 (коэф. сложности)
        Минимум 5000 HP, даже если игроков 0.
        """
        if active_players < 1:
            active_players = 1
            
        avg_damage_per_workout = 350
        workouts_per_week = 3
        difficulty_multiplier = 1.2
        
        target_hp = active_players * avg_damage_per_workout * workouts_per_week * difficulty_multiplier
        return int(max(1000, target_hp))
    
    @staticmethod
    def calculate_reward_pool(max_hp: int, traits: dict) -> int:
        """
        Расчет общего банка монет.
        База: 1 монета за 10 HP.
        Множители за сложность.
        """
        base_pool = max_hp / 10
        multiplier = 1.0
        
        # Бонусы за трейты
        if traits.get("armor_reduction"):
            multiplier += 0.3 # +30% монет за броню
        if traits.get("evasion_chance"):
            multiplier += 0.3 # +30% за уворот
        if traits.get("regen_daily_percent"):
            multiplier += 0.5 # +50% за регенерацию (бесячий трейт)
            
        return int(base_pool * multiplier)

    @staticmethod
    def create_boss(active_players: int) -> Raid:
        # 1. Определяем тип босса (шансы)
        roll = random.random()
        
        boss_type = "normal"
        traits = {}
        name_suffix = ""
        
        if roll < 0.40: 
            # 40% Обычный
            boss_type = "normal"
        elif roll < 0.55:
            # 15% Бронированный (Снижает урон на 50%, пока не пробьют)
            boss_type = "armored"
            traits = {"armor_reduction": 0.5} 
            name_suffix = "the Ironclad"
        elif roll < 0.70:
            # 15% Ловкий (20% шанс уворота)
            boss_type = "agile"
            traits = {"evasion_chance": 20}
            name_suffix = "the Phantom"
        elif roll < 0.85:
            # 15% Радиоактивный (Реген 5% HP в сутки - реализуем при атаке или джобе)
            boss_type = "radioactive"
            traits = {"regen_daily_percent": 0.05}
            name_suffix = "the Toxic"
        else:
            # 15% Рой/Мелкие (Мало HP, но это просто визуализация "стаи")
            # Для механики сделаем просто -20% HP от нормы, но имя другое
            boss_type = "swarm"
            name_suffix = "Swarm"

        # 2. Генерируем Имя
        base_name = f"{random.choice(BossFactory.PREFIXES)} of {random.choice(BossFactory.NAMES)}"
        final_name = f"{base_name} {name_suffix}".strip()
        
        # 3. Считаем HP
        hp = BossFactory.calculate_hp(active_players)
        
        # Корректировки HP по типу
        if boss_type == "swarm":
            hp = int(hp * 0.8) # Стаю легче убить (по хп), но их много (визуально)
        if boss_type == "armored":
            hp = int(hp * 1.1) # Бронированный чуть жирнее

        return Raid(
            boss_name=final_name,
            boss_type=boss_type,
            max_hp=hp,
            current_hp=hp,
            traits=traits,
            active_debuffs={}
        )