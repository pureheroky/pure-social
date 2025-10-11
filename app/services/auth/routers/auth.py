from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from ..schemas import (
    UserAuthLogin,
    UserAuthRegister,
    UserUpdateRefresh,
)
from ..services import (
    login_user,
    refresh_tokens,
    register_user,
    verify_token,
    set_auth_cookies,
    set_logout_cookies,
)
from services.users.schemas import UserData

router = APIRouter()

@router.post("/login", response_model=UserData)
async def user_login(data: UserAuthLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and set HttpOnly cookies."""
    access_token, refresh_token, user = await login_user(data, db)
    response = JSONResponse(
        content=user.model_dump(),
        status_code=200
    )
    set_auth_cookies(response, access_token, refresh_token)
    return response

@router.post("/register", response_model=UserData, status_code=201)
async def user_register(data: UserAuthRegister, db: AsyncSession = Depends(get_db)):
    """Register new user and set HttpOnly cookies."""
    access_token, refresh_token, user = await register_user(data, db)
    response = JSONResponse(
        content=user.model_dump(),
        status_code=201
    )
    set_auth_cookies(response, access_token, refresh_token)
    return response

@router.post("/token/refresh", response_model=UserData)
async def refresh_token(data: UserUpdateRefresh, db: AsyncSession = Depends(get_db)):
    """Refresh user tokens."""
    access_token, refresh_token, user = await refresh_tokens(data.refresh_token, db)
    response = JSONResponse(
        content=user.model_dump(),
        status_code=200
    )
    set_auth_cookies(response, access_token, refresh_token)
    return response

@router.get("/verify", response_model=UserData)
async def verify_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Verify access token and return user data."""
    user_email = getattr(request.state, "user_email", None)
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    user = await verify_token(user_email, db)
    return user.model_dump()

@router.post("/logout")
async def user_logout(db: AsyncSession = Depends(get_db)):
    """Clear HttpOnly cookies."""
    response = JSONResponse(content={"message": "Logged out"}, status_code=200)
    set_logout_cookies(response)
    return response