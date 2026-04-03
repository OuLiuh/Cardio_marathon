import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pytz

from database import init_models, get_db
from models import User, Raid, RaidLog, UserUpgrade
from schemas import (
    WorkoutData, AttackResult, RaidState, LogDisplay,
    UserRead, UserCreate, RaidParticipant,
    ShopItemRead, ShopBuyRequest
)
from mechanics import get_strategy
from boss_factory import BossFactory
from shop_config import SHOP_ITEMS
from ocr_service import UniversalParser

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Pulse Guardian Backend...")
    max_retries = 5
    for i in range(max_retries):
        try:
            await init_models()
            logger.info("✅ Database is ready!")
            break
        except Exception as e:
            logger.error(f"⚠️ DB Connection failed: {e}")
            if i < max_retries - 1:
                await asyncio.sleep(5)
            else:
                logger.error("❌ Fatal: Could not connect to DB")
    yield


app = FastAPI(lifespan=lifespan)


# --- API ENDPOINTS ---

@app.post("/api/attack", response_model=AttackResult)
async def process_attack(workout_data: WorkoutData, db: AsyncSession = Depends(get_db)):
    """
    Обработка атаки с валидацией данных по типам спорта.
    """
    try:
        # 1. ЗАЩИТА И ВАЛИДАЦИЯ (Бизнес-логика)
        # Проверка специально для бега
        if workout_data.sport_type == "run":
            if workout_data.distance_km <= 0 or workout_data.duration_minutes <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Некорректные данные для бега. "
                        f"Распознано: дистанция {workout_data.distance_km} км, "
                        f"время {workout_data.duration_minutes} мин. "
                        f"Для бега эти показатели не могут быть нулевыми."
                    )
                )

        # Общая проверка для всех остальных активностей
        elif workout_data.distance_km <= 0 and workout_data.duration_minutes <= 0 and workout_data.calories <= 0:
            raise HTTPException(
                status_code=400,
                detail="Данные тренировки не распознаны или пусты. Попробуйте другое фото."
            )

        # 2. Получение данных из БД
        user_result = await db.execute(select(User).where(User.id == workout_data.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        raid_result = await db.execute(select(Raid).where(Raid.is_active == True))
        raid = raid_result.scalar_one_or_none()
        if not raid:
            raid = await BossFactory.create_random_boss(db)
            await db.commit()
            await db.refresh(raid)

        # 3. Расчет механики урона
        strategy = get_strategy(workout_data.sport_type)

        upgrades_result = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user.id))
        upgrades = upgrades_result.scalars().all()
        upgrade_map = {upg.item_key: upg.level for upg in upgrades}

        calc_result = strategy.calculate(workout_data, upgrade_map, raid.traits)
        damage_to_deal = min(calc_result.damage, raid.current_hp)

        # 4. Применение изменений
        raid.current_hp -= damage_to_deal
        user.xp += calc_result.xp_earned
        user.gold += calc_result.gold_earned

        # Повышение уровня
        new_level = (user.xp // 1000) + 1
        if new_level > user.level:
            user.level = new_level

        # Сообщение лога
        msg = f"Удар на {damage_to_deal}!"
        if calc_result.is_miss:
            msg = "💨 Босс УВЕРНУЛСЯ!"
        elif damage_to_deal > 0:
            if calc_result.is_crit:
                msg = f"💥 КРИТ! Нанесено {damage_to_deal} урона!"
            else:
                msg = f"⚔️ Нанесено {damage_to_deal} урона."

        # Создание записи в логе (без raw_text)
        new_log = RaidLog(
            raid_id=raid.id,
            user_id=user.id,
            damage=damage_to_deal,
            sport_type=workout_data.sport_type,
            message=msg
        )
        db.add(new_log)
        await db.flush()

        # 5. Проверка финала рейда (без дублирования!)
        if raid.current_hp <= 0:
            raid.current_hp = 0
            raid.is_active = False
            msg += " ☠️ БОСС ПОВЕРЖЕН!"

            # Награда всем участникам
            participants_result = await db.execute(
                select(User).join(RaidLog).where(RaidLog.raid_id == raid.id).distinct()
            )
            for p in participants_result.scalars().all():
                p.gold += 50

            await BossFactory.create_random_boss(db)

        await db.commit()

        return AttackResult(
            damage_dealt=damage_to_deal,
            xp_earned=calc_result.xp_earned,
            gold_earned=calc_result.gold_earned,
            message=msg
        )

    except HTTPException as he:
        # Пробрасываем наши ошибки валидации (400) наверх
        raise he
    except Exception as e:
        logger.error(f"❌ Critical Error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка сервера при обработке атаки")


@app.get("/api/raid/state", response_model=RaidState)
async def get_raid_state(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Raid).where(Raid.is_active == True))
    raid = result.scalar_one_or_none()

    if not raid:
        raid = await BossFactory.create_random_boss(db)
        await db.commit()
        await db.refresh(raid)

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
            message=log.message
        ) for log, username in logs_result
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
        active_debuffs=raid.active_debuffs or {},
        active_players_count=len(participants),
        recent_logs=display_logs,
        participants=participants
    )


@app.get("/api/users/{user_id}", response_model=UserRead)
async def get_user_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/api/users/register", response_model=UserRead)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_data.id))
    existing = result.scalar_one_or_none()
    if existing: return existing

    new_user = User(
        id=user_data.id,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.get("/api/shop/{user_id}", response_model=List[ShopItemRead])
async def get_shop(user_id: int, db: AsyncSession = Depends(get_db)):
    upgrades_result = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user_id))
    upgrades = upgrades_result.scalars().all()
    user_upgrades = {u.item_key: u.level for u in upgrades}

    shop_list = []
    for key, item in SHOP_ITEMS.items():
        current_lvl = user_upgrades.get(key, 0)
        is_maxed = current_lvl >= item["max_level"]
        price = item["base_price"] * (current_lvl + 1) if not is_maxed else 0

        shop_list.append(ShopItemRead(
            key=key, name=item["name"], description=item["description"],
            sport_type=item["sport_type"], current_level=current_lvl,
            max_level=item["max_level"], next_price=price,
            is_locked=False, is_maxed=is_maxed
        ))
    return shop_list


@app.post("/api/shop/buy")
async def buy_upgrade(request: ShopBuyRequest, db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    user = user_result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")

    item_cfg = SHOP_ITEMS.get(request.item_key)
    if not item_cfg: raise HTTPException(status_code=400, detail="Invalid item")

    upg_result = await db.execute(
        select(UserUpgrade).where(UserUpgrade.user_id == user.id, UserUpgrade.item_key == request.item_key)
    )
    upgrade = upg_result.scalar_one_or_none()
    current_lvl = upgrade.level if upgrade else 0

    if current_lvl >= item_cfg["max_level"]:
        raise HTTPException(status_code=400, detail="Max level reached")

    price = item_cfg["base_price"] * (current_lvl + 1)
    if user.gold < price:
        raise HTTPException(status_code=400, detail="Not enough gold")

    user.gold -= price
    if upgrade:
        upgrade.level += 1
    else:
        db.add(UserUpgrade(user_id=user.id, item_key=request.item_key, level=1))

    await db.commit()
    return {"message": "Улучшение куплено!", "new_gold": user.gold}


@app.post("/api/ocr")
async def perform_ocr(
        user_id: int = Form(...),
        sport_type: str = Form(...),
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db)
):
    try:
        content = await file.read()
        parser = UniversalParser(user_id, sport_type)
        workout_data = parser.parse(content)
        return workout_data
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при распознавании текста")