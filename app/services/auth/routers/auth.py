from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from ..schemas import (
    UserAuthResponse,
    UserAuthLogin,
    UserAuthRegister,
    UserUpdateRefresh,
)
from ..services import login_user, refresh_tokens, register_user


router = APIRouter()


@router.post("/login", response_model=UserAuthResponse)
async def user_login(data: UserAuthLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return tokens."""
    access_token, refresh_token = await login_user(data, db)
    return UserAuthResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserAuthResponse, status_code=201)
async def user_register(data: UserAuthRegister, db: AsyncSession = Depends(get_db)):
    """Register new user and return tokens."""
    access_token, refresh_token = await register_user(data, db)
    return UserAuthResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/token/refresh", response_model=UserAuthResponse)
async def refresh_token(data: UserUpdateRefresh, db: AsyncSession = Depends(get_db)):
    """Refresh user tokens."""
    access_token, refresh_token = await refresh_tokens(data.refresh_token, db)
    return UserAuthResponse(access_token=access_token, refresh_token=refresh_token)
