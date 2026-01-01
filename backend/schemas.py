# backend/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Входные данные от фронтенда (после тренировки)
class WorkoutData(BaseModel):
    user_id: int
    sport_type: str = Field(..., description="run, cycle, swim, football")
    duration_minutes: int
    calories: int
    distance_km: Optional[float] = 0.0
    avg_heart_rate: Optional[int] = 0
    
# Ответ после атаки
class AttackResult(BaseModel):
    damage_dealt: int
    gold_earned: int
    xp_earned: int
    is_critical: bool
    new_boss_hp: int
    message: str # Например: "Критический удар! Броня пробита!"

# Состояние рейда для отображения всем
# Добавь маленькую модель для отображения игрока на арене
class RaidParticipant(BaseModel):
    username: str
    level: int
    avatar_color: str # Для красоты генерируем цвет
class RaidState(BaseModel):
    boss_name: str
    max_hp: int
    current_hp: int
    active_debuffs: dict
    active_players_count: int
    recent_logs: List["LogDisplay"]
    participants: List[RaidParticipant]

class LogDisplay(BaseModel):
    username: str
    damage: int
    sport_type: str
    created_at: datetime

# Для регистрации/проверки
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    id: int # Telegram ID обязательно

class UserUpdate(UserBase):
    pass # Тут только username

class UserRead(UserBase):
    id: int
    level: int
    xp: int
    gold: int
    
    class Config:
        from_attributes = True