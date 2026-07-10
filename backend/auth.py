# backend/auth.py
"""
Аутентификация: хеширование паролей (bcrypt) и JWT-токены.
user_id всегда извлекается из токена — никогда из тела запроса.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SECRET_KEY
from database import get_db
from models import User

# --- Настройки ---

# Алгоритм подписи JWT
ALGORITHM = "HS256"
# Срок жизни access-токена (развлекательный проект — длинная сессия, без refresh-токенов)
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Хеширование паролей через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2-схема: токен читается из заголовка Authorization: Bearer <token>
# tokenUrl нужен только для генерации OpenAPI-документации (swagger)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет пароль против сохранённого хеша."""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str) -> str:
    """
    Генерирует JWT с payload:
      - sub: id пользователя (строка — стандартное поле JWT)
      - username: логин
      - exp: время истечения
    """
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI-зависимость: извлекает и валидирует JWT из заголовка Authorization,
    затем подгружает пользователя из БД.

    Используется в защищённых эндпоинтах:
        current_user: User = Depends(get_current_user)

    При невалидном/просроченном токене или удалённом пользователе — 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (InvalidTokenError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user
