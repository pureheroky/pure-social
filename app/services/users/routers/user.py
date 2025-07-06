from typing import List
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from ..schemas import FriendshipData, UserData
from ..services import (
    get_user_by_id,
    upload_avatar_pic,
    all_friends,
    request_friend,
    accept_or_decline_friend,
    request_friend_status,
    delete_friend,
)

router = APIRouter()


@router.get("/get_user/", response_model=UserData)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await get_user_by_id(user_id, db)


@router.post("/upload_avatar/", response_model=UserData)
async def upload_avatar(
    user_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    return await upload_avatar_pic(user_id, file, db)


@router.get("/friendship/friends", response_model=List[UserData])
async def friends_all(user_id: int, db: AsyncSession = Depends(get_db)):
    return await all_friends(user_id, "accepted", "outgoing", db)


@router.get("/friendship/friends/incoming", response_model=List[UserData])
async def friends_incoming(user_id: int, db: AsyncSession = Depends(get_db)):
    return await all_friends(user_id, "requested", "incoming", db)


@router.post("/friendship/request", response_model=FriendshipData)
async def friend_request(
    user_id: int, friend_id: int, db: AsyncSession = Depends(get_db)
):
    return await request_friend(user_id, friend_id, db)


@router.get("/friendship/request/status", response_model=FriendshipData)
async def friend_request_status(
    user_id: int, friend_id: int, db: AsyncSession = Depends(get_db)
):
    return request_friend_status(user_id, friend_id, db)


@router.patch("/friendship/accept", response_model=FriendshipData)
async def friend_accept(
    user_id: int, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await accept_or_decline_friend(user_id, requested_id, "accept", db)


@router.patch("/friendship/decline", response_model=FriendshipData)
async def friend_decline(
    user_id: int, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await accept_or_decline_friend(user_id, requested_id, "decline", db)


@router.delete("/friendship/delete")
async def friend_delete(
    user_id: int, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await delete_friend(user_id, requested_id, db)
