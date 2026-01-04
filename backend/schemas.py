from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Входные данные от фронтенда (после тренировки)
class WorkoutData(BaseModel):
    user_id: int
    sport_type: str = Field(..., description="run, cycle, swim, football")
    # Поля по умолчанию 0, чтобы не ломать логику математики
    duration_minutes: Optional[int] = 0
    calories: Optional[int] = 0
    distance_km: Optional[float] = 0.0
    avg_heart_rate: Optional[int] = 0
    
# Ответ после атаки
class AttackResult(BaseModel):
    damage_dealt: int
    gold_earned: int
    xp_earned: int
    is_critical: bool
    new_boss_hp: int
    message: str 

# Состояние рейда
class RaidParticipant(BaseModel):
    username: str
    level: int
    avatar_color: str 
    
class LogDisplay(BaseModel):
    username: str
    damage: int
    sport_type: str
    created_at: datetime

class RaidState(BaseModel):
    boss_name: str
    boss_type: str 
    traits: dict   
    max_hp: int
    current_hp: int
    active_debuffs: dict
    active_players_count: int
    recent_logs: List[LogDisplay] # Исправил кавычки, если LogDisplay объявлен выше
    participants: List[RaidParticipant]

# Для регистрации/проверки
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    id: int 

class UserUpdate(UserBase):
    pass 

class UserRead(UserBase):
    id: int
    level: int
    xp: int
    gold: int
    
    class Config:
        from_attributes = True