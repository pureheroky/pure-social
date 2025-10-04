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
    """Generate access and refresh tokens, update user's refresh token."""
    access = generate_access_token(email)
    refresh = generate_refresh_token(email)
    user.refresh_token = refresh
    return access, refresh


async def login_user(data: UserAuthLogin, db: AsyncSession) -> tuple[str, str]:
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

    async def operation() -> tuple[str, str]:
        return _setup_tokens(data.email, user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully logged in user {data.email}",
        "Error while logging user in",
        logger,
        use_flush=True,
    )


async def register_user(data: UserAuthRegister, db: AsyncSession) -> tuple[str, str]:
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

    async def operation() -> tuple[str, str]:
        db.add(new_user)
        await db.flush()  # Generate ID early for logging
        logger.info(f"Created user with id {new_user.id}")
        return _setup_tokens(data.email, new_user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully registered new user {data.email} (id={new_user.id})",
        "Error while registering new user",
        logger,
        refresh_object=new_user,
        use_flush=True,
    )


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> tuple[str, str]:
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

    async def operation() -> tuple[str, str]:
        return _setup_tokens(user_email, user)

    return await execute_db_operation(
        db,
        operation,
        f"Tokens successfully refreshed for {user_email}",
        "Error while refreshing user tokens",
        logger,
        use_flush=True,
    )
