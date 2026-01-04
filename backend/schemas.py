# backend/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Входные данные от фронтенда
class WorkoutData(BaseModel):
    user_id: int
    sport_type: str = Field(..., description="run, cycle, swim, football")
    # Теперь эти поля опциональны, так как зависят от типа спорта
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

# Состояние рейда для отображения всем
# Добавь маленькую модель для отображения игрока на арене
class RaidParticipant(BaseModel):
    username: str
    level: int
    avatar_color: str 

class RaidState(BaseModel):
    boss_name: str
    boss_type: str 
    traits: dict   
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