# backend/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- SHOP SCHEMAS ---
class ShopItemRead(BaseModel):
    key: str
    name: str
    description: str
    sport_type: str
    current_level: int
    max_level: int
    next_price: int
    is_locked: bool
    is_maxed: bool

class ShopBuyRequest(BaseModel):
    item_key: str

# --- AUTH SCHEMAS ---

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=4, max_length=128)

class UserLogin(BaseModel):
    username: str
    password: str

class UserRead(UserBase):
    id: int
    level: int
    xp: int
    gold: int
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

# --- RAID / WORKOUT ---

class RaidParticipant(BaseModel):
    username: str
    level: int
    avatar_color: str 

class LogDisplay(BaseModel):
    username: str
    damage: int
    sport_type: str
    created_at: datetime
    message: Optional[str] = None

class RaidState(BaseModel):
    boss_name: str
    boss_type: str 
    traits: dict   
    max_hp: int
    current_hp: int
    active_debuffs: dict
    active_players_count: int
    recent_logs: List[LogDisplay]
    participants: List[RaidParticipant]

class WorkoutData(BaseModel):
    user_id: Optional[int] = None
    sport_type: str = Field(..., description="run, cycle, swim, football")
    duration_minutes: Optional[int] = 0
    calories: Optional[int] = 0
    distance_km: Optional[float] = 0.0
    avg_heart_rate: Optional[int] = 0
    raw_text: Optional[str] = None

    class Config:
        extra = "allow"
    
class AttackResult(BaseModel):
    damage_dealt: int
    gold_earned: int
    xp_earned: int
    is_critical: bool
    new_boss_hp: int
    message: str 
