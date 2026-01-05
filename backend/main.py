# backend/main.py
import asyncio
from contextlib import asynccontextmanager
# ДОБАВЬТЕ List В ЭТУ СТРОКУ:
from typing import Annotated, List 

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import pytz

from database import init_models, get_db
# Убедитесь, что UserUpgrade добавлен сюда:
from models import User, Raid, RaidLog, UserUpgrade 
# Убедитесь, что ShopItemRead и ShopBuyRequest добавлены сюда:
from schemas import (
    WorkoutData, AttackResult, RaidState, LogDisplay, 
    UserRead, UserCreate, UserUpdate, RaidParticipant,
    ShopItemRead, ShopBuyRequest
)
from mechanics import get_strategy
from boss_factory import BossFactory
# Убедитесь, что конфиг магазина импортирован:
from shop_config import SHOP_ITEMS, SHOP_REGISTRY

# --- 1. Lifespan (Запуск и инициализация БД) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    События жизненного цикла:
    Запускается один раз при старте сервера.
    Пытается создать таблицы в БД.
    """
    print("🚀 Starting Pulse Guardian Backend...")
    
    max_retries = 5
    for i in range(max_retries):
        try:
            print(f"🔄 Connecting to DB and checking tables ({i+1}/{max_retries})...")
            await init_models() # Эта функция из database.py
            print("✅ Database is ready!")
            break
        except Exception as e:
            print(f"⚠️ DB Connection failed: {e}")
            if i < max_retries - 1:
                await asyncio.sleep(5)
            else:
                print("❌ Fatal: Could not connect to DB.")
                raise e
                
    yield # Здесь приложение работает и принимает запросы
    
    print("🛑 Shutting down...")

# --- 2. Инициализация приложения ---
app = FastAPI(
    title="Pulse Guardian API",
    lifespan=lifespan
)

# --- 3. Роуты (API Endpoints) ---

# 1. Проверка: существует ли пользователь?
@app.get("/api/user/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 2. Регистрация нового пользователя
@app.post("/api/user/register", response_model=UserRead)
async def register_user(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    # Проверяем, вдруг уже есть (защита от дублей)
    existing_user = await db.get(User, user_data.id)
    if existing_user:
        return existing_user # Просто возвращаем его
        
    new_user = User(
        id=user_data.id, 
        username=user_data.username,
        level=1, 
        xp=0, 
        gold=0
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

# 3. Смена ника
@app.put("/api/user/{user_id}", response_model=UserRead)
async def update_user(user_id: int, data: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.username = data.username
    await db.commit()
    await db.refresh(user)
    return user

# Хелпер для получения количества игроков
async def get_total_users_count(db: AsyncSession) -> int:
    """Считает всех зарегистрированных пользователей в БД"""
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar()
    # Если пользователей 0 или None, возвращаем 1, чтобы математика не ломалась
    return count if count and count > 0 else 1

# === SHOP ENDPOINTS ===

@app.get("/api/shop/{user_id}", response_model=List[ShopItemRead])
async def get_shop(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    # Получаем текущие улучшения пользователя
    result = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user_id))
    user_upgrades_list = result.scalars().all()
    
    # Словарь {key: level}
    current_levels = {u.upgrade_key: u.level for u in user_upgrades_list}
    
    response = []
    for item in SHOP_ITEMS:
        lvl = current_levels.get(item.key, 0)
        is_max = lvl >= item.max_level
        
        # Проверяем доступность (пререквизиты)
        locked = item.is_locked(current_levels)
        
        response.append(ShopItemRead(
            key=item.key,
            name=item.name,
            description=item.description,
            sport_type=item.sport_type,
            current_level=lvl,
            max_level=item.max_level,
            next_price=item.get_price(lvl),
            is_locked=locked,
            is_maxed=is_max
        ))
    return response

@app.post("/api/shop/buy")
async def buy_item(req: ShopBuyRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    # 1. Юзер
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 2. Товар
    item = SHOP_REGISTRY.get(req.item_key)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    # 3. Текущее состояние
    result = await db.execute(
        select(UserUpgrade)
        .where(UserUpgrade.user_id == req.user_id, UserUpgrade.upgrade_key == req.item_key)
    )
    upgrade_entry = result.scalars().first()
    current_level = upgrade_entry.level if upgrade_entry else 0
    
    # 4. Проверки
    if current_level >= item.max_level:
        raise HTTPException(status_code=400, detail="Max level reached")
        
    price = item.get_price(current_level)
    if user.gold < price:
        raise HTTPException(status_code=400, detail="Not enough gold")
        
    # Для проверки блокировки (супер-апгрейды) нужно знать все уровни юзера
    all_upgrades_res = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == req.user_id))
    all_upgrades = {u.upgrade_key: u.level for u in all_upgrades_res.scalars().all()}
    
    if item.is_locked(all_upgrades):
        raise HTTPException(status_code=400, detail="Item is locked (requirements not met)")

    # 5. Покупка
    user.gold -= price
    
    if upgrade_entry:
        upgrade_entry.level += 1
    else:
        new_entry = UserUpgrade(user_id=user.id, upgrade_key=item.key, level=1)
        db.add(new_entry)
        
    await db.commit()
    return {"status": "ok", "new_level": current_level + 1, "gold_left": user.gold}

# === ATTACK LOGIC UPDATE ===

@app.post("/api/attack", response_model=AttackResult)
async def process_attack(
    workout: WorkoutData, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await db.get(User, workout.user_id)
    if not user:
        user = User(id=workout.user_id, username="Unknown Hero")
        db.add(user)
        await db.flush() 
    
    upgrades_dict = {u.upgrade_key: u.level for u in user.upgrades}

    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    if not raid:
        total_users = await get_total_users_count(db)
        raid = BossFactory.create_boss(total_users)
        db.add(raid)
        await db.flush()

    # Токсик реген
    if raid.traits.get("regen_daily_percent") and raid.current_hp > 0:
        heal = int(raid.max_hp * 0.005)
        raid.current_hp = min(raid.max_hp, raid.current_hp + heal)

    StrategyClass = get_strategy(workout.sport_type)
    # ПЕРЕДАЕМ АПГРЕЙДЫ В СТРАТЕГИЮ
    strategy = StrategyClass(workout, user.level, raid.active_debuffs, raid.traits, upgrades_dict)
    calc_result = strategy.calculate()
    
    damage_to_deal = calc_result.damage
    raid.current_hp = max(0, raid.current_hp - damage_to_deal)
    
    if calc_result.applied_debuffs:
        new_debuffs = raid.active_debuffs.copy()
        new_debuffs.update(calc_result.applied_debuffs)
        raid.active_debuffs = new_debuffs

    gold_gain = 0 
    xp_gain = 100
    if calc_result.is_miss: xp_gain = 10
    
    user.xp += xp_gain
    if user.xp >= user.level * 1000:
        user.level += 1
        user.xp -= user.level * 1000

    current_log = RaidLog(
        raid_id=raid.id,
        user_id=user.id,
        sport_type=workout.sport_type,
        damage=damage_to_deal,
        gold_earned=0,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        is_miss=calc_result.is_miss
    )
    db.add(current_log)
    await db.flush()

    msg = f"Удар на {damage_to_deal}!"
    if calc_result.is_miss: msg = "💨 Босс УВЕРНУЛСЯ!"
    elif calc_result.is_crit: msg = "🔥 КРИТИЧЕСКИЙ УДАР!"
    if "armor_break" in calc_result.applied_debuffs: msg += " 🛡️ Броня расколота!"

    if raid.current_hp == 0:
        raid.is_active = False
        msg += " ☠️ БОСС ПОВЕРЖЕН!"
        total_pool = BossFactory.calculate_reward_pool(raid.max_hp, raid.traits)
        
        stats_result = await db.execute(
            select(RaidLog.user_id, func.sum(RaidLog.damage))
            .where(RaidLog.raid_id == raid.id)
            .group_by(RaidLog.user_id)
        )
        user_stats = stats_result.all()
        total_raid_damage = sum(dmg for _, dmg in user_stats)
        
        if total_raid_damage > 0:
            for uid, dmg in user_stats:
                share = dmg / total_raid_damage
                payout = int(total_pool * share)
                if uid == user.id:
                    user.gold += payout
                    gold_gain = payout
                else:
                    p_user = await db.get(User, uid)
                    if p_user: p_user.gold += payout
            msg += f" Награда: {gold_gain} 🪙"

        total_users = await get_total_users_count(db)
        new_raid = BossFactory.create_boss(total_users)
        db.add(new_raid)

    await db.commit()

    return AttackResult(
        damage_dealt=damage_to_deal,
        gold_earned=gold_gain,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        new_boss_hp=raid.current_hp,
        message=msg
    )

@app.get("/api/raid/current", response_model=RaidState)
async def get_current_raid(db: Annotated[AsyncSession, Depends(get_db)]):
    # 1. Босс
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    # 2. ПОЛУЧЕНИЕ УЧАСТНИКОВ (Вынесем это выше, чтобы использовать даже если босса нет, или оставим пустым)
    # Для простоты, если босса нет, вернем пустой список, как и было
    
    # === ИСПРАВЛЕНИЕ 1: Блок, если босса нет ===
    if not raid:
        return RaidState(
            boss_name="Waiting...",
            boss_type="normal",     # <--- ДОБАВЛЕНО (заглушка)
            traits={},              # <--- ДОБАВЛЕНО (заглушка)
            max_hp=100, 
            current_hp=0, 
            active_debuffs={}, 
            active_players_count=0, 
            recent_logs=[], 
            participants=[]
        )
    
    # 3. Логи (как было)
    logs_result = await db.execute(
        select(RaidLog, User.username)
        .join(User, RaidLog.user_id == User.id)
        .where(RaidLog.raid_id == raid.id)
        .order_by(RaidLog.created_at.desc())
        .limit(5)
    )
    
    display_logs = []
    for log, username in logs_result:
        display_logs.append(LogDisplay(
            username=username or f"Hero",
            damage=log.damage,
            sport_type=log.sport_type,
            created_at=log.created_at
        ))

    # 4. Участники
    users_result = await db.execute(select(User).limit(12))
    users = users_result.scalars().all()
    
    participants = []
    for u in users:
        colors = ["#e94560", "#0f3460", "#533483", "#e62e2d", "#f2a365", "#222831", "#00adb5"]
        color = colors[u.id % len(colors)]
        
        participants.append(RaidParticipant(
            username=u.username or "Hero",
            level=u.level,
            avatar_color=color
        ))

    total_players = len(users)

    # === ИСПРАВЛЕНИЕ 2: Финальный возврат ===
    return RaidState(
        boss_name=raid.boss_name,
        boss_type=raid.boss_type, # <--- ДОБАВЛЕНО: берем из БД
        traits=raid.traits,       # <--- ДОБАВЛЕНО: берем из БД
        max_hp=raid.max_hp,
        current_hp=raid.current_hp,
        active_debuffs=raid.active_debuffs,
        active_players_count=total_players,
        recent_logs=display_logs,
        participants=participants
    )

@app.get("/api/health")
async def health_check():
    """Простой эндпоинт для проверки, что сервер жив"""
    return {"status": "ok"}