# backend/models.py
from sqlalchemy import BigInteger, String, Float, Integer, Boolean, JSON, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import List

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    
    logs: Mapped[List["RaidLog"]] = relationship(back_populates="user")
    upgrades: Mapped[List["UserUpgrade"]] = relationship(back_populates="user", lazy="selectin")

class UserUpgrade(Base):
    __tablename__ = "user_upgrades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    upgrade_key: Mapped[str] = mapped_column(String) # Ключ улучшения (run_watch, etc)
    level: Mapped[int] = mapped_column(Integer, default=0)
    
    user: Mapped["User"] = relationship(back_populates="upgrades")

    # Уникальность: у юзера может быть только одна запись про конкретный апгрейд
    __table_args__ = (UniqueConstraint('user_id', 'upgrade_key', name='_user_upgrade_uc'),)

class Raid(Base):
    __tablename__ = "raids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boss_name: Mapped[str] = mapped_column(String)
    boss_type: Mapped[str] = mapped_column(String, default="normal")
    
    max_hp: Mapped[int] = mapped_column(Integer)
    current_hp: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Дебаффы, наложенные игроками (пробитая броня и т.д.)
    active_debuffs: Mapped[dict] = mapped_column(JSON, default={})
    
    # Врожденные характеристики босса (шанс уворота %, % защиты брони, % регена)
    traits: Mapped[dict] = mapped_column(JSON, default={}) 
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class RaidLog(Base):
    __tablename__ = "raid_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raid_id: Mapped[int] = mapped_column(ForeignKey("raids.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    sport_type: Mapped[str] = mapped_column(String)
    damage: Mapped[int] = mapped_column(Integer)
    gold_earned: Mapped[int] = mapped_column(Integer)
    xp_earned: Mapped[int] = mapped_column(Integer)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Добавляем поле, чтобы знать, увернулся ли босс
    is_miss: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    user: Mapped["User"] = relationship(back_populates="logs")