from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import result
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
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
import logging

setup_log("auth")
logger = logging.getLogger()

async def login_user(data: UserAuthLogin, db: AsyncSession):
    logger.info(f"Trying to log in user: {data.model_dump()}")
    result = await db.execute(select(User).filter_by(email=data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, str(user.password_hash)):
        logger.warning(f"Unknown user: {data.model_dump()}")
        raise HTTPException(status_code=401, detail="Email or password is wrong")

    access = generate_access_token(data.email)
    refresh = generate_refresh_token(data.email)

    user.refresh_token = refresh

    return access, refresh
    

async def register_user(data: UserAuthRegister, db: AsyncSession):
    logger.info(f"Trying to register user: {data.model_dump()}")
    result = await db.execute(
        select(User).filter(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.warning(f"Not existing user: {data.model_dump()}")
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

    try:
        db.add(new_user)
        await db.flush()
        access = generate_access_token(data.email)
        refresh = generate_refresh_token(data.email)
        new_user.refresh_token = refresh
        await db.commit()
        logger.info(f"Successfully registered new user: {[new_user.__dict__]}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while registering new user: {e}")
        raise HTTPException(status_code=500, detail="Error while creating new user")

    return access, refresh
        

async def refresh_tokens(refresh_token: str, db: AsyncSession):
    logger.info(f"Updating token: {refresh_token}")
    try:
        payload = decode_token(refresh_token)
        user_email = payload["sub"]
    except:
        logger.error(f"Error while updating token - token is not correct: {refresh_token}")
        raise HTTPException(
            status_code=502, detail="Provided token is not correct"
        )
    result = await db.execute(select(User).filter_by(email=user_email))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"Error while updating token - user with that email does not exist: {refresh_token}")
        raise HTTPException(
            status_code=401, detail="User with that email does not exist"
        )

    if not user.refresh_token:
        logger.error(f"Error while updating token - token does not exist: {refresh_token}")
        raise HTTPException(status_code=401, detail="Refresh token does not exist")

    if refresh_token != user.refresh_token:
        logger.error(f"Error while updating token - token is not the same as in database: {refresh_token}")
        raise HTTPException(
            status_code=401, detail="Provided token is not the same as in database"
        )

    access = generate_access_token(user_email)
    refresh = generate_refresh_token(user_email)

    user.refresh_token = refresh

    logger.error(f"Token successfully updated: {refresh}")
    return access, refresh
