from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from ..schemas import (
    UserAuthResponse,
    UserAuthLogin,
    UserAuthRegister,
    UserUpdateRefresh,
)
from ..services import login_user, refresh_tokens, register_user, verify_token
from services.users.schemas import UserData
from db.models.user import User

router = APIRouter()


@router.post("/login", response_model=UserAuthResponse)
async def user_login(data: UserAuthLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return tokens."""
    access_token, refresh_token, user = await login_user(data, db)
    return UserAuthResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.post("/register", response_model=UserAuthResponse, status_code=201)
async def user_register(data: UserAuthRegister, db: AsyncSession = Depends(get_db)):
    """Register new user and return tokens."""
    access_token, refresh_token, user = await register_user(data, db)
    return UserAuthResponse(
        access_token=access_token, refresh_token=refresh_token, user=user
    )


@router.post("/token/refresh", response_model=UserAuthResponse)
async def refresh_token(data: UserUpdateRefresh, db: AsyncSession = Depends(get_db)):
    """Refresh user tokens."""
    access_token, refresh_token = await refresh_tokens(data.refresh_token, db)
    return UserAuthResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/verify", response_model=UserData)
async def verify_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Verify access token and return user data."""
    user_email = getattr(request.state, "user_email", None)
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return await verify_token(user_email, db)
