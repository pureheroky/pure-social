from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from ..schemas import UserAuthLogin, UserAuthRegister
from ..services import login_user, register_user, refresh_tokens, verify_token, logout_user
from services.users.schemas import UserData

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


@router.post("/login", response_model=UserData)
async def user_login(data: UserAuthLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and set HttpOnly cookies."""
    return await login_user(data, db)


@router.post("/register", response_model=UserData, status_code=201)
async def user_register(data: UserAuthRegister, db: AsyncSession = Depends(get_db)):
    """Register new user and set HttpOnly cookies."""
    return await register_user(data, db)


@router.post("/token/refresh", response_model=UserData)
async def refresh_token_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """Refresh tokens using refresh token from HttpOnly cookie."""
    return await refresh_tokens(request, db)


@router.get("/verify", response_model=UserData)
async def verify_user(request: Request, db: AsyncSession = Depends(get_db)):
    """Verify access token and return user data."""
    user_email = getattr(request.state, "user_email", None)
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    user = await verify_token(user_email, db)
    return user.model_dump()


@router.post("/logout")
async def user_logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Logout user: clear refresh token in DB and remove HttpOnly cookies."""
    return await logout_user(request, db)
