from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from services.users.schemas import UserData
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
from core.config import get_settings
import os

logger = setup_log("auth", __name__)
settings = get_settings()

def _setup_tokens(email: str, user: User) -> tuple[str, str]:
    """Generate access and refresh tokens, update user's refresh token."""
    access = generate_access_token(email)
    refresh = generate_refresh_token(email)
    user.refresh_token = refresh
    return access, refresh

def set_auth_cookies(response: JSONResponse, access_token: str, refresh_token: str):
    """Set HttpOnly cookies for access and refresh tokens on the response."""
    is_secure = os.getenv("ENV") == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_TTL,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_TTL,
        path="/",
    )

def set_logout_cookies(response: JSONResponse):
    """Set expired cookies to clear access and refresh tokens."""
    is_secure = os.getenv("ENV") == "production"
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=is_secure,
        samesite="strict",
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        secure=is_secure,
        samesite="strict",
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        path="/",
    )

async def login_user(data: UserAuthLogin, db: AsyncSession) -> tuple[str, str, UserData]:
    """Authenticate user login and generate tokens."""
    logger.info(f"Trying to log in user email: {data.email[:5]}...")
    result = await db.execute(select(User).filter_by(email=data.email))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Unknown user email: {data.email[:5]}...")
        raise HTTPException(status_code=404, detail="User does not exist")

    if not verify_password(data.password, str(user.password_hash)):
        logger.warning(f"Wrong password for email: {data.email[:5]}...")
        raise HTTPException(status_code=401, detail="Wrong password")

    async def operation() -> tuple[str, str, UserData]:
        access, refresh = _setup_tokens(data.email, user)
        return access, refresh, UserData.model_validate(user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully logged in user {data.email}",
        "Error while logging user in",
        logger,
        use_flush=True,
    )

async def register_user(
    data: UserAuthRegister, db: AsyncSession
) -> tuple[str, str, UserData]:
    """Register a new user and generate tokens."""
    logger.info(f"Trying to register user email: {data.email[:5]}...")
    result = await db.execute(
        select(User).filter(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.warning(
            f"User already exists: email {data.email[:5]}... or username {data.username}"
        )
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

    async def operation() -> tuple[str, str, UserData]:
        db.add(new_user)
        await db.flush()
        logger.info(f"Created user with id {new_user.id}")
        access, refresh = _setup_tokens(data.email, new_user)
        return access, refresh, UserData.model_validate(new_user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully registered new user {data.email} (id={new_user.id})",
        "Error while registering new user",
        logger,
        refresh_object=new_user,
        use_flush=True,
    )

async def refresh_tokens(refresh_token: str, db: AsyncSession) -> tuple[str, str, UserData]:
    """Refresh access and refresh tokens using valid refresh token."""
    logger.info(f"Refreshing tokens for token: {refresh_token[:10]}...")
    try:
        payload = decode_token(refresh_token)
        user_email = payload["sub"]
    except Exception:
        logger.error(f"Invalid refresh token: {refresh_token[:10]}...")
        raise HTTPException(status_code=401, detail="Provided token is not correct")

    result = await db.execute(select(User).filter_by(email=user_email))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"User not found for email: {user_email[:5]}...")
        raise HTTPException(
            status_code=401, detail="User with that email does not exist"
        )

    if not user.refresh_token:
        logger.error(f"No refresh token stored for user: {user_email[:5]}...")
        raise HTTPException(status_code=401, detail="Refresh token does not exist")

    if refresh_token != user.refresh_token:
        logger.error(f"Token mismatch for user: {user_email[:5]}...")
        raise HTTPException(
            status_code=401, detail="Provided token does not match stored token"
        )

    async def operation() -> tuple[str, str, UserData]:
        access, refresh = _setup_tokens(user_email, user)
        return access, refresh, UserData.model_validate(user)

    return await execute_db_operation(
        db,
        operation,
        f"Tokens successfully refreshed for {user_email}",
        "Error while refreshing user tokens",
        logger,
        use_flush=True,
    )

async def logout_user(db: AsyncSession) -> dict:
    """Clear tokens in DB and return logout response."""
    return {"message": "Logged out"}

async def verify_token(user_email: str, db: AsyncSession) -> UserData:
    """Verify token and return user data."""
    logger.info(f"Verifying token for user: {user_email[:5]}...")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).filter_by(email=user_email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserData.model_validate(user)