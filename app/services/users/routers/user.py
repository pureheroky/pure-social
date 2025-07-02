from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from ..schemas import UserData
from ..services import get_user_by_id, upload_avatar_pic

router = APIRouter()


@router.get("/get_user/", response_model=UserData)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_id(user_id, db)
    return user


@router.post("/upload_avatar/", response_model=UserData)
async def upload_avatar(
    user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    user = await upload_avatar_pic(user_id, file, db)
    return user
