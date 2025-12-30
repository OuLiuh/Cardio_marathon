# backend/models.py
from sqlalchemy import BigInteger, String, Float, Integer, Boolean, JSON, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Telegram ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    
    # Связь с атаками
    logs: Mapped[List["RaidLog"]] = relationship(back_populates="user")

class Raid(Base):
    __tablename__ = "raids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boss_name: Mapped[str] = mapped_column(String)
    max_hp: Mapped[int] = mapped_column(Integer)
    current_hp: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Храним активные дебаффы как JSON: {"armor_break": true, "armor_break_expires": "ISO_DATE"}
    active_debuffs: Mapped[dict] = mapped_column(JSON, default={})
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class RaidLog(Base):
    """История атак (кто, когда, чем и насколько сильно ударил)"""
    __tablename__ = "raid_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raid_id: Mapped[int] = mapped_column(ForeignKey("raids.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    sport_type: Mapped[str] = mapped_column(String) # run, swim, cycle, football
    damage: Mapped[int] = mapped_column(Integer)
    gold_earned: Mapped[int] = mapped_column(Integer)
    xp_earned: Mapped[int] = mapped_column(Integer)
    
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    user: Mapped["User"] = relationship(back_populates="logs")