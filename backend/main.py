import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import pytz

from boss_factory import BossFactory

# Импорты из твоих модулей
# config импортируется внутри database.py, здесь он явно не нужен, 
# если мы не используем переменные напрямую в main.py
from database import init_models, get_db
from models import User, Raid, RaidLog
from schemas import WorkoutData, AttackResult, RaidState, LogDisplay, UserRead, UserCreate, UserUpdate, RaidParticipant
from mechanics import get_strategy

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

# Хелпер для получения количества активных игроков (за последнюю неделю)
async def get_active_player_count(db: AsyncSession) -> int:
    # Считаем уникальных юзеров в логах за 7 дней
    seven_days_ago = datetime.now(pytz.utc) - timedelta(days=7)
    result = await db.execute(
        select(func.count(func.distinct(RaidLog.user_id)))
        .where(RaidLog.created_at >= seven_days_ago)
    )
    count = result.scalar()
    # Если игра новая, берем просто всех юзеров
    if count == 0:
        total_users = await db.execute(select(func.count(User.id)))
        count = total_users.scalar()
    return count if count > 0 else 1

@app.post("/api/attack", response_model=AttackResult)
async def process_attack(
    workout: WorkoutData, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    # А. Юзер (код тот же)
    user = await db.get(User, workout.user_id)
    if not user:
        user = User(id=workout.user_id, username="Unknown Hero")
        db.add(user)
        await db.flush() 
    
    # Б. Получаем активный Рейд
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    # === ГЕНЕРАЦИЯ ЕСЛИ НЕТ БОССА ===
    if not raid:
        active_count = await get_active_player_count(db)
        raid = BossFactory.create_boss(active_count)
        db.add(raid)
        await db.flush()

    # === ЛОГИКА РАДИОАКТИВНОГО БОССА (РЕГЕНЕРАЦИЯ) ===
    # Проверяем, прошла ли суточная отсечка с момента создания или прошлого регена
    # Для упрощения: просто проверяем, наступил ли новый день относительно created_at
    # (В реальном проде лучше хранить last_regen_time, но для MVP можно опустить)
    if raid.traits.get("regen_daily_percent"):
        # Тут нужна логика, но чтобы не спамить регеном при каждой атаке, 
        # оставим пока просто как характеристику "Регенерирует 1% прямо во время атаки" 
        # или просто пропустим сложную временную логику. 
        # Давай сделаем так: Радиоактивный босс лечится на 0.5% при каждой атаке по нему!
        # Это проще и веселее (игроки видят сопротивление).
        heal = int(raid.max_hp * 0.005)
        raid.current_hp = min(raid.max_hp, raid.current_hp + heal)

    # В. Расчет механики
    StrategyClass = get_strategy(workout.sport_type)
    
    # Передаем traits
    strategy = StrategyClass(workout, user.level, raid.active_debuffs, raid.traits)
    calc_result = strategy.calculate()
    
    # Г. Применение
    # Если был промах (is_miss), урон 0
    damage_to_deal = calc_result.damage
    raid.current_hp = max(0, raid.current_hp - damage_to_deal)
    
    if calc_result.applied_debuffs:
        new_debuffs = raid.active_debuffs.copy()
        new_debuffs.update(calc_result.applied_debuffs)
        raid.active_debuffs = new_debuffs

    # Д. Смерть и Респаун
    if raid.current_hp == 0:
        raid.is_active = False
        # Бонус за убийство
        user.gold += 500
        
        # === МГНОВЕННЫЙ РЕСПАУН ===
        active_count = await get_active_player_count(db)
        new_raid = BossFactory.create_boss(active_count)
        db.add(new_raid)
        # Старый коммитим как inactive, новый как active

    # Е. Награды игроку (как было)
    gold_gain = int(damage_to_deal / 10)
    xp_gain = 100
    if calc_result.is_miss: 
        gold_gain = 0 # За промах нет золота
        
    user.gold += gold_gain
    user.xp += xp_gain
    
    # Level Up логика (оставляем старую)
    if user.xp >= user.level * 1000:
        user.level += 1
        user.xp -= user.level * 1000

    # Ж. Лог
    log = RaidLog(
        raid_id=raid.id,
        user_id=user.id,
        sport_type=workout.sport_type,
        damage=damage_to_deal,
        gold_earned=gold_gain,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        is_miss=calc_result.is_miss # <--- Пишем в лог
    )
    db.add(log)
    
    await db.commit()
    
    # Формируем сообщение
    msg = f"Удар на {damage_to_deal}!"
    if calc_result.is_miss:
        msg = "💨 Босс УВЕРНУЛСЯ! (0 урона)"
    elif calc_result.is_crit:
        msg = "🔥 КРИТИЧЕСКИЙ УДАР!"
        
    if "armor_break" in calc_result.applied_debuffs:
        msg += " 🛡️ Броня расколота!"
    
    # Если босс умер в эту атаку
    if raid.current_hp == 0:
        msg += " ☠️ БОСС ПОВЕРЖЕН! Появляется новый..."

    return AttackResult(
        damage_dealt=damage_to_deal,
        gold_earned=gold_gain,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        new_boss_hp=raid.current_hp, # Вернется 0 для старого, фронт обновится через поллинг и увидит нового
        message=msg
    )

@app.get("/api/raid/current", response_model=RaidState)
async def get_current_raid(db: Annotated[AsyncSession, Depends(get_db)]):
    # 1. Босс
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    # Заглушка, если босса нет
    if not raid:
        return RaidState(
            boss_name="Waiting...", max_hp=100, current_hp=0, 
            active_debuffs={}, active_players_count=0, recent_logs=[], participants=[]
        )
    
    # 2. Логи (как было)
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

    # 3. ПОЛУЧЕНИЕ УЧАСТНИКОВ (НОВОЕ)
    # Берем топ-12 активных игроков (сортировка по уровню или просто всех)
    users_result = await db.execute(select(User).limit(12))
    users = users_result.scalars().all()
    
    participants = []
    for u in users:
        # Генерируем цвет на основе ID (чтобы у каждого был свой постоянный цвет)
        colors = ["#e94560", "#0f3460", "#533483", "#e62e2d", "#f2a365", "#222831", "#00adb5"]
        color = colors[u.id % len(colors)]
        
        participants.append(RaidParticipant(
            username=u.username or "Hero",
            level=u.level,
            avatar_color=color
        ))

    # Кол-во игроков
    total_players = len(users)

    return RaidState(
        boss_name=raid.boss_name,
        max_hp=raid.max_hp,
        current_hp=raid.current_hp,
        active_debuffs=raid.active_debuffs,
        active_players_count=total_players,
        recent_logs=display_logs,
        participants=participants # <--- Передаем
    )

@app.get("/api/health")
async def health_check():
    """Простой эндпоинт для проверки, что сервер жив"""
    return {"status": "ok"}