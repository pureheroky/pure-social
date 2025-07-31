from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from utils.db_utils import execute_db_operation
from db.models.user import User
from .schemas import UserAuthLogin, UserAuthRegister
from core.security import (
    decode_token,
    generate_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from utils.logger import setup_log

logger = setup_log("auth", __name__)


def _setup_tokens(email: str, user: User) -> tuple[str, str]:
    access = generate_access_token(email)
    refresh = generate_refresh_token(email)
    user.refresh_token = refresh
    return access, refresh


async def login_user(data: UserAuthLogin, db: AsyncSession) -> tuple[str, str]:
    logger.info(f"Trying to log in user: {data.model_dump()}")
    result = await db.execute(select(User).filter_by(email=data.email))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Unknown user: {data.model_dump()}")
        raise HTTPException(status_code=404, detail="User does not exist")

    if not verify_password(data.password, str(user.password_hash)):
        logger.warning(f"Wrong password: {data.model_dump()}")
        raise HTTPException(status_code=401, detail="Wrong password")

    return await execute_db_operation(
        db,
        lambda: _setup_tokens(data.email, user),
        f"Successfully logged in user {data.email}",
        "Error while logging user in",
        logger,
    )


async def register_user(data: UserAuthRegister, db: AsyncSession) -> tuple[str, str]:
    logger.info(f"Trying to register user: {data.model_dump()}")
    result = await db.execute(
        select(User).filter(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.warning(f"User already exists: {data.model_dump()}")
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = hash_password(data.password)
    now = datetime.now(timezone.utc)

    new_user = User(
        name=data.name,
        created_at=now,
        updated_at=now,
        age=data.age,
        username=data.username,
        email=data.email,
        password_hash=hashed,
        custom_url=data.username,
        refresh_token=None,
    )

    return await execute_db_operation(
        db,
        lambda: (
            db.add(new_user),
            _setup_tokens(data.email, new_user),
        )[-1],
        f"Successfully registered new user {data.email} (id={new_user.id})",
        "Error while registering new user",
        logger,
    )


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
    logger.info(f"Updating token: {refresh_token}")
    try:
        payload = decode_token(refresh_token)
        user_email = payload["sub"]
    except Exception:
        logger.error(
            f"Error while updating token - token is not correct: {refresh_token}"
        )
        raise HTTPException(status_code=401, detail="Provided token is not correct")
    result = await db.execute(select(User).filter_by(email=user_email))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(
            f"Error while updating token - user with that email does not exist: {refresh_token}"
        )
        raise HTTPException(
            status_code=401, detail="User with that email does not exist"
        )

    if not user.refresh_token:
        logger.error(
            f"Error while updating token - token does not exist: {refresh_token}"
        )
        raise HTTPException(status_code=401, detail="Refresh token does not exist")

    if refresh_token != user.refresh_token:
        logger.error(
            f"Error while updating token - token is not the same as in database: {refresh_token}"
        )
        raise HTTPException(
            status_code=401, detail="Provided token is not the same as in database"
        )

    return await execute_db_operation(
        db,
        lambda: _setup_tokens(user_email, user),
        f"Token successfully updated for {user_email}",
        "Error while updating user tokens",
        logger,
    )