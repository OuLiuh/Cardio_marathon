import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, List
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
import pytz

from database import init_models, get_db
from models import User, Raid, RaidLog, UserUpgrade
from schemas import (
    WorkoutData, AttackResult, RaidState, LogDisplay,
    UserRead, UserCreate, UserUpdate, RaidParticipant,
    ShopItemRead, ShopBuyRequest
)
from mechanics import get_strategy
from boss_factory import BossFactory
from shop_config import SHOP_ITEMS, SHOP_REGISTRY
from ocr_service import UniversalParser  # Убедитесь, что путь правильный

# --- Lifespan: Инициализация при старте ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting Pulse Guardian Backend...")
    max_retries = 5
    for i in range(max_retries):
        try:
            print(f"🔄 Connecting to DB and checking tables ({i+1}/{max_retries})...")
            await init_models()
            print("✅ Database is ready!")
            break
        except Exception as e:
            print(f"⚠️ DB Connection failed: {e}")
            if i < max_retries - 1:
                await asyncio.sleep(5)
            else:
                print("❌ Fatal: Could not connect to DB.")
                raise e
    yield

# --- Инициализация приложения ---
app = FastAPI(title="Pulse Guardian API", lifespan=lifespan)

# --- OCR: Распознавание тренировки по фото ---
@app.post("/api/scan-workout", response_model=WorkoutData)
async def scan_workout(
    user_id: int = Form(...),
    sport_type: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Принимает фото тренировки, распознаёт данные через OCR.
    Возвращает предварительные данные без сохранения.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    image_bytes = await file.read()
    parser = UniversalParser(user_id=user_id, sport_type=sport_type)

    try:
        workout_data = parser.parse_image(image_bytes)
        return workout_data
    except Exception as e:
        print(f"OCR Error: {e}")
        return WorkoutData(user_id=user_id, sport_type=sport_type)

# --- Пользователь: получение, регистрация, обновление ---
@app.get("/api/user/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/user/register", response_model=UserRead)
async def register_user(user_data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existing_user = await db.get(User, user_data.id)
    if existing_user:
        return existing_user
    new_user = User(id=user_data.id, username=user_data.username, level=1, xp=0, gold=0)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.put("/api/user/{user_id}", response_model=UserRead)
async def update_user(user_id: int, data: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.username = data.username
    await db.commit()
    await db.refresh(user)
    return user

# --- Магазин: просмотр и покупка улучшений ---
@app.get("/api/shop/{user_id}", response_model=List[ShopItemRead])
async def get_shop(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user_id))
    user_upgrades_list = result.scalars().all()
    current_levels = {u.upgrade_key: u.level for u in user_upgrades_list}

    response = []
    for item in SHOP_ITEMS:
        lvl = current_levels.get(item.key, 0)
        is_max = lvl >= item.max_level
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
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    item = SHOP_REGISTRY.get(req.item_key)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    result = await db.execute(
        select(UserUpgrade).where(UserUpgrade.user_id == req.user_id, UserUpgrade.upgrade_key == req.item_key)
    )
    upgrade_entry = result.scalars().first()
    current_level = upgrade_entry.level if upgrade_entry else 0

    if current_level >= item.max_level:
        raise HTTPException(status_code=400, detail="Max level reached")

    price = item.get_price(current_level)
    if user.gold < price:
        raise HTTPException(status_code=400, detail="Not enough gold")

    all_upgrades_res = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == req.user_id))
    all_upgrades = {u.upgrade_key: u.level for u in all_upgrades_res.scalars().all()}
    if item.is_locked(all_upgrades):
        raise HTTPException(status_code=400, detail="Item is locked (requirements not met)")

    user.gold -= price
    if upgrade_entry:
        upgrade_entry.level += 1
    else:
        new_entry = UserUpgrade(user_id=user.id, upgrade_key=item.key, level=1)
        db.add(new_entry)

    await db.commit()
    return {"status": "ok", "new_level": current_level + 1, "gold_left": user.gold}

# --- Атака: обработка тренировки и нанесение урона боссу ---
@app.post("/api/attack", response_model=AttackResult)
async def process_attack(workout: WorkoutData, db: Annotated[AsyncSession, Depends(get_db)]):
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

    if raid.traits.get("regen_daily_percent") and raid.current_hp > 0:
        heal = int(raid.max_hp * 0.005)
        raid.current_hp = min(raid.max_hp, raid.current_hp + heal)

    StrategyClass = get_strategy(workout.sport_type)
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
    if calc_result.is_miss:
        xp_gain = 10

    user.xp += xp_gain
    if user.xp >= user.level * 1000:
        user.level += 1
        user.xp -= user.level * 1000

    current_log = RaidLog(
        raid_id=raid.id,
        user_id=user.id,
        sport_type=workout.sport_type,
        damage=damage_to_deal,
        gold_earned=gold_gain,
        xp_earned=xp_gain,
        is_critical=calc_result.is_crit,
        is_miss=calc_result.is_miss,
        message=msg  # <-- Добавлено
    )

    db.add(current_log)
    await db.flush()

    msg = f"Удар на {damage_to_deal}!"
    if calc_result.is_miss:
        msg = "💨 Босс УВЕРНУЛСЯ!"
    elif calc_result.is_crit:
        msg = "🔥 КРИТИЧЕСКИЙ УДАР!"
    if "armor_break" in calc_result.applied_debuffs:
        msg += " 🛡️ Броня расколота!"

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
                    if p_user:
                        p_user.gold += payout
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

# --- Получение текущего состояния рейда ---
@app.get("/api/raid/current", response_model=RaidState)
async def get_current_raid(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalars().first()

    if not raid:
        return RaidState(
            boss_name="Waiting...",
            boss_type="normal",
            traits={},
            max_hp=100,
            current_hp=0,
            active_debuffs={},
            active_players_count=0,
            recent_logs=[],
            participants=[]
        )

    logs_result = await db.execute(
        select(RaidLog, User.username)
        .join(User, RaidLog.user_id == User.id)
        .where(RaidLog.raid_id == raid.id)
        .order_by(RaidLog.created_at.desc())
        .limit(5)
    )
    display_logs = [
        LogDisplay(
            username=username or "Hero",
            damage=log.damage,
            sport_type=log.sport_type,
            created_at=log.created_at,
            message=log.message  # <-- теперь передаётся
        )
        for log, username in logs_result
    ]

    users_result = await db.execute(select(User).limit(12))
    users = users_result.scalars().all()
    participants = []
    colors = ["#e94560", "#0f3460", "#533483", "#e62e2d", "#f2a365", "#222831", "#00adb5"]
    for u in users:
        participants.append(RaidParticipant(
            username=u.username or "Hero",
            level=u.level,
            avatar_color=colors[u.id % len(colors)]
        ))

    return RaidState(
        boss_name=raid.boss_name,
        boss_type=raid.boss_type,
        traits=raid.traits,
        max_hp=raid.max_hp,
        current_hp=raid.current_hp,
        active_debuffs=raid.active_debuffs,
        active_players_count=len(users),
        recent_logs=display_logs,
        participants=participants
    )

# --- Health check ---
@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# --- Хелпер: количество пользователей ---
async def get_total_users_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar()
    return max(count, 1)