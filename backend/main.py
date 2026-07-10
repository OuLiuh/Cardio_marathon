import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import init_models, get_db
from models import User, Raid, RaidLog, UserUpgrade
from schemas import (
    WorkoutData, AttackResult, RaidState, LogDisplay,
    UserRead, UserCreate, UserLogin, TokenResponse, RaidParticipant,
    ShopItemRead, ShopBuyRequest
)
from auth import (
    hash_password, verify_password, create_access_token, get_current_user
)
from mechanics import get_strategy
from boss_factory import BossFactory
from shop_config import SHOP_REGISTRY
from ocr_service import UniversalParser

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.json()
        raw_text = body.get('raw_text', '') if body else ''

        error_details = []
        for error in exc.errors():
            loc = ' -> '.join(str(x) for x in error.get('loc', []))
            msg = error.get('msg', '')
            error_details.append(f"{loc}: {msg}")

        detail_msg = "Ошибка валидации: " + "; ".join(error_details)
        if raw_text:
            detail_msg += f"\n\n📄 Распознанный текст:\n{raw_text}"

        return JSONResponse(
            status_code=422,
            content={"detail": detail_msg}
        )
    except Exception as e:
        logger.error(f"Error in validation handler: {e}")
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)}
        )


# --- AUTH ---

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    username = user_data.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Имя должно быть не короче 2 символов")

    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Такое имя уже занято")

    user = User(
        username=username,
        password_hash=hash_password(user_data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user=user)


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == credentials.username.strip())
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user=user)


@app.get("/api/user/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- ATTACK ---

@app.post("/api/attack", response_model=AttackResult)
async def process_attack(
    workout_data: WorkoutData,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if workout_data.sport_type == "run":
            if workout_data.distance_km <= 0 or workout_data.duration_minutes <= 0:
                detail_msg = (
                    f"Данные бега не валидны. Расстояние: {workout_data.distance_km} км, "
                    f"Время: {workout_data.duration_minutes} мин. "
                    f"Пожалуйста, используйте более четкое фото."
                )
                if workout_data.raw_text:
                    detail_msg += f"\n\n📄 Распознанный текст:\n{workout_data.raw_text}"
                raise HTTPException(status_code=400, detail=detail_msg)
        elif workout_data.distance_km <= 0 and workout_data.duration_minutes <= 0 and workout_data.calories <= 0:
            detail_msg = "Не удалось распознать данные тренировки. Попробуйте снова."
            if workout_data.raw_text:
                detail_msg += f"\n\n📄 Распознанный текст:\n{workout_data.raw_text}"
            raise HTTPException(status_code=400, detail=detail_msg)

        user = current_user

        raid_result = await db.execute(select(Raid).where(Raid.is_active == True))
        raid = raid_result.scalar_one_or_none()
        if not raid:
            raid = await BossFactory.create_random_boss(db)
            await db.commit()
            await db.refresh(raid)

        strategy_class = get_strategy(workout_data.sport_type)
        upgrades_result = await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user.id))
        upgrades = upgrades_result.scalars().all()
        upgrade_map = {upg.upgrade_key: upg.level for upg in upgrades}

        strategy = strategy_class(
            data=workout_data,
            user_level=user.level,
            raid_debuffs=raid.active_debuffs or {},
            boss_traits=raid.traits or {},
            user_upgrades=upgrade_map
        )
        calc_result = strategy.calculate()
        damage_to_deal = min(calc_result.damage, raid.current_hp)

        xp_gain = 10 if calc_result.is_miss else 100
        gold_gain = 0

        raid.current_hp -= damage_to_deal
        user.xp += xp_gain
        user.gold += gold_gain

        new_level = (user.xp // 1000) + 1
        if new_level > user.level:
            user.level = new_level

        msg = f"Удар на {damage_to_deal}!"
        if calc_result.is_miss:
            msg = "💨 Босс УВЕРНУЛСЯ!"
        elif damage_to_deal > 0:
            if calc_result.is_crit:
                msg = f"💥 КРИТ! Нанесено {damage_to_deal} урона!"
            else:
                msg = f"⚔️ Нанесено {damage_to_deal} урона."

        new_log = RaidLog(
            raid_id=raid.id,
            user_id=user.id,
            damage=damage_to_deal,
            sport_type=workout_data.sport_type,
            gold_earned=gold_gain,
            xp_earned=xp_gain,
            is_critical=calc_result.is_crit,
            is_miss=calc_result.is_miss
        )
        db.add(new_log)
        await db.flush()

        if raid.current_hp <= 0:
            raid.current_hp = 0
            raid.is_active = False
            msg += " ☠️ БОСС ПОВЕРЖЕН!"

            participants_result = await db.execute(
                select(User).join(RaidLog).where(RaidLog.raid_id == raid.id).distinct()
            )
            for p in participants_result.scalars().all():
                p.gold += 50
                if p.id == user.id:
                    gold_gain += 50

            await BossFactory.create_random_boss(db)

        await db.commit()

        return AttackResult(
            damage_dealt=damage_to_deal,
            xp_earned=xp_gain,
            gold_earned=gold_gain,
            is_critical=calc_result.is_crit,
            new_boss_hp=raid.current_hp,
            message=msg
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Attack error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка сервера при обработке атаки")


# --- RAID ---

@app.get("/api/raid/state")
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
            message=f"Удар на {log.damage}!" if log.damage > 0 else "💨 Босс УВЕРНУЛСЯ!"
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


@app.get("/api/raid/current", response_model=RaidState)
async def get_raid_current_alias(db: AsyncSession = Depends(get_db)):
    return await get_raid_state(db)


# --- SHOP ---

@app.get("/api/shop", response_model=List[ShopItemRead])
async def get_shop(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        upgrades_result = await db.execute(
            select(UserUpgrade).where(UserUpgrade.user_id == current_user.id)
        )
        upgrades = upgrades_result.scalars().all()
        user_upgrades = {u.upgrade_key: u.level for u in upgrades}

        shop_list = []
        for key, item in SHOP_REGISTRY.items():
            current_lvl = user_upgrades.get(key, 0)
            is_maxed = current_lvl >= item.max_level
            price = item.base_price * (current_lvl + 1) if not is_maxed else 0
            is_locked = item.is_locked(user_upgrades)

            shop_list.append(ShopItemRead(
                key=key, name=item.name, description=item.description,
                sport_type=item.sport_type, current_level=current_lvl,
                max_level=item.max_level, next_price=price,
                is_locked=is_locked, is_maxed=is_maxed
            ))
        return shop_list
    except Exception as e:
        logger.error(f"Shop error: {e}", exc_info=True)
        raise


@app.post("/api/shop/buy")
async def buy_upgrade(
    request: ShopBuyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = current_user

    item_cfg = SHOP_REGISTRY.get(request.item_key)
    if not item_cfg:
        raise HTTPException(status_code=400, detail="Invalid item")

    upg_result = await db.execute(
        select(UserUpgrade).where(
            UserUpgrade.user_id == user.id,
            UserUpgrade.upgrade_key == request.item_key,
        )
    )
    upgrade = upg_result.scalar_one_or_none()
    current_lvl = upgrade.level if upgrade else 0

    if current_lvl >= item_cfg.max_level:
        raise HTTPException(status_code=400, detail="Max level reached")

    user_upgrades = {
        u.upgrade_key: u.level
        for u in (
            await db.execute(select(UserUpgrade).where(UserUpgrade.user_id == user.id))
        ).scalars().all()
    }
    if item_cfg.is_locked(user_upgrades):
        raise HTTPException(status_code=400, detail="Item is locked")

    price = item_cfg.base_price * (current_lvl + 1)
    if user.gold < price:
        raise HTTPException(status_code=400, detail="Not enough gold")

    user.gold -= price
    if upgrade:
        upgrade.level += 1
    else:
        db.add(UserUpgrade(user_id=user.id, upgrade_key=request.item_key, level=1))

    await db.commit()
    return {"message": "Success", "new_gold": user.gold}


# --- OCR ---

@app.post("/api/scan-workout", response_model=WorkoutData)
async def scan_workout(
    sport_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"OCR: user_id={current_user.id}, sport_type={sport_type}, file={file.filename}"
    )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Файл должен быть изображением")

    try:
        image_bytes = await file.read()
        parser = UniversalParser(user_id=current_user.id, sport_type=sport_type)
        workout_data = await parser.parse_image(image_bytes)
        return workout_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка OCR: {str(e)}")
