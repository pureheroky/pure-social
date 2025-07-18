from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

from ..schemas import PostCreate, PostData
from ..services import create_post, get_posts

router = APIRouter()

@router.get("/get_posts", response_model=List[PostData])
async def get_user_posts(request: Request, db: AsyncSession = Depends(get_db)):
    return await get_posts(request.state.user_email, db)

@router.post("/create_post", response_model=PostData)
async def create_user_post(request: Request, data: PostCreate, db: AsyncSession = Depends(get_db)):
    return await create_post(request.state.user_email, data, db)