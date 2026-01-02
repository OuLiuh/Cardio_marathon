import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

# Импорты из твоих модулей
# config импортируется внутри database.py, здесь он явно не нужен, 
# если мы не используем переменные напрямую в main.py
from database import init_models, get_db
from models import User, Raid, RaidLog
from schemas import WorkoutData, AttackResult, RaidState, LogDisplay, UserRead, UserCreate, UserUpdate
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

@app.post("/api/attack", response_model=AttackResult)
async def process_attack(
    workout: WorkoutData, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Основной метод атаки.
    Принимает данные тренировки -> Считает урон -> Обновляет Босса и Юзера.
    """
    
    # А. Получаем или создаем пользователя
    # Используем get, так как ищем по Primary Key
    user = await db.get(User, workout.user_id)
    
    if not user:
        # Если юзер новый - создаем. Username можно будет обновить позже через WebApp data
        user = User(id=workout.user_id, username="Unknown Hero")
        db.add(user)
        # Делаем flush, чтобы объект зафиксировался в сессии, но пока не коммитим окончательно
        await db.flush() 
    
    # Б. Получаем активный Рейд (Босса)
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    if not raid:
        # Если босса нет (убили или первый запуск), создаем нового
        raid = Raid(
            boss_name="Titan of Sloth", 
            max_hp=50000, 
            current_hp=50000,
            active_debuffs={}
        )
        db.add(raid)
        await db.flush()

    # В. Расчет механики (Стратегия)
    StrategyClass = get_strategy(workout.sport_type)
    
    # Передаем данные, уровень юзера и текущие дебаффы босса
    strategy = StrategyClass(workout, user.level, raid.active_debuffs)
    calc_result = strategy.calculate()
    
    # Г. Применение результатов
    
    # 1. Наносим урон боссу
    raid.current_hp = max(0, raid.current_hp - calc_result.damage)
    
    # 2. Обновляем дебаффы босса (если есть новые)
    if calc_result.applied_debuffs:
        # Копируем и обновляем словарь, чтобы SQLAlchemy увидел изменение JSON поля
        new_debuffs = raid.active_debuffs.copy()
        new_debuffs.update(calc_result.applied_debuffs)
        raid.active_debuffs = new_debuffs

    # 3. Проверка смерти босса
    if raid.current_hp == 0:
        raid.is_active = False
        # Здесь можно добавить логику "Мега-награды" за убийство
        # Например: user.gold += 500

    # 4. Начисляем награды игроку
    gold_gain = int(calc_result.damage / 10) # 1 монета за 10 урона
    xp_gain = 100 # Базовый опыт за тренировку
    
    user.gold += gold_gain
    user.xp += xp_gain
    
    # Простейшая логика Level Up
    xp_to_next_level = user.level * 1000
    if user.xp >= xp_to_next_level:
        user.level += 1
        user.xp = user.xp - xp_to_next_level # Оставляем остаток опыта

    # Д. Логируем атаку в историю
    log = RaidLog(
        raid_id=raid.id,
        user_id=user.id,
        sport_type=workout.sport_type,
        damage=calc_result.damage,
        gold_earned=gold_gain,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit
    )
    db.add(log)
    
    # Е. Финальное сохранение всего в БД
    await db.commit()
    
    # Формируем сообщение для фронта
    msg = "Удар нанесен!"
    if calc_result.is_crit:
        msg = "КРИТИЧЕСКИЙ УДАР!"
    if "armor_break" in calc_result.applied_debuffs:
        msg += " Броня Босса пробита!"

    return AttackResult(
        damage_dealt=calc_result.damage,
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