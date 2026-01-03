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
    # А. Юзер (Получаем/Создаем)
    user = await db.get(User, workout.user_id)
    if not user:
        user = User(id=workout.user_id, username="Unknown Hero")
        db.add(user)
        await db.flush() 
    
    # Б. Рейд (Получаем/Создаем)
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()
    
    if not raid:
        active_count = await get_active_player_count(db)
        raid = BossFactory.create_boss(active_count)
        db.add(raid)
        await db.flush()

    # В. Механика и Трейты
    # --- ЛОГИКА РЕГЕНЕРАЦИИ (Toxic) ---
    if raid.traits.get("regen_daily_percent") and raid.current_hp > 0:
        heal = int(raid.max_hp * 0.005) # 0.5% отхил при ударе
        raid.current_hp = min(raid.max_hp, raid.current_hp + heal)

    StrategyClass = get_strategy(workout.sport_type)
    strategy = StrategyClass(workout, user.level, raid.active_debuffs, raid.traits)
    calc_result = strategy.calculate()
    
    damage_to_deal = calc_result.damage
    raid.current_hp = max(0, raid.current_hp - damage_to_deal)
    
    if calc_result.applied_debuffs:
        new_debuffs = raid.active_debuffs.copy()
        new_debuffs.update(calc_result.applied_debuffs)
        raid.active_debuffs = new_debuffs

    # Г. Награды (Gold теперь 0, XP даем сразу)
    gold_gain = 0 
    xp_gain = 100
    if calc_result.is_miss:
        xp_gain = 10 # Утешительный опыт
    
    user.xp += xp_gain
    if user.xp >= user.level * 1000:
        user.level += 1
        user.xp -= user.level * 1000

    # Д. Логируем атаку СЕЙЧАС (до распределения наград, чтобы учесть этот урон)
    current_log = RaidLog(
        raid_id=raid.id,
        user_id=user.id,
        sport_type=workout.sport_type,
        damage=damage_to_deal,
        gold_earned=0, # Пока 0, золото только в конце
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        is_miss=calc_result.is_miss
    )
    db.add(current_log)
    
    # Делаем flush, чтобы этот лог попал в транзакцию и учитывался в SELECT ниже
    await db.flush()

    msg = f"Удар на {damage_to_deal}!"
    if calc_result.is_miss: msg = "💨 Босс УВЕРНУЛСЯ!"
    elif calc_result.is_crit: msg = "🔥 КРИТИЧЕСКИЙ УДАР!"
    if "armor_break" in calc_result.applied_debuffs: msg += " 🛡️ Броня расколота!"

    # Е. Смерть босса и РАСПРЕДЕЛЕНИЕ НАГРАД
    if raid.current_hp == 0:
        raid.is_active = False
        msg += " ☠️ БОСС ПОВЕРЖЕН!"

        # 1. Считаем общий пул
        total_pool = BossFactory.calculate_reward_pool(raid.max_hp, raid.traits)
        
        # 2. Считаем суммарный урон по боссу (учитывая только что нанесенный)
        # Сумма damage из RaidLog для текущего raid_id
        stats_result = await db.execute(
            select(RaidLog.user_id, func.sum(RaidLog.damage))
            .where(RaidLog.raid_id == raid.id)
            .group_by(RaidLog.user_id)
        )
        user_stats = stats_result.all() # Список кортежей [(user_id, total_dmg), ...]
        
        total_raid_damage = sum(dmg for _, dmg in user_stats)
        
        if total_raid_damage > 0:
            # 3. Раздаем награды
            distrib_msg = []
            
            # Получаем объекты пользователей для обновления
            participant_ids = [uid for uid, _ in user_stats]
            # Используем execute для массового обновления или цикл с get (цикл проще для MVP)
            
            for uid, dmg in user_stats:
                share = dmg / total_raid_damage
                payout = int(total_pool * share)
                
                # Если это текущий юзер, обновляем объект в памяти
                if uid == user.id:
                    user.gold += payout
                    gold_gain = payout # Чтобы вернуть в ответе API
                else:
                    # Для остальных - обновляем в БД
                    # Внимание: внутри одной транзакции лучше не делать лишних SELECT
                    # Но здесь придется достать юзера
                    p_user = await db.get(User, uid)
                    if p_user:
                        p_user.gold += payout
            
            msg += f" Награда: {gold_gain} 🪙 (Всего: {total_pool})"

        # 4. Респаун
        active_count = await get_active_player_count(db)
        new_raid = BossFactory.create_boss(active_count)
        db.add(new_raid)

    # Ж. Финальный коммит
    await db.commit()

    return AttackResult(
        damage_dealt=damage_to_deal,
        gold_earned=gold_gain, # Будет > 0 только если босс умер
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