from typing import List
from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from ..schemas import FriendshipData, UserData
from ..services import (
    get_user_with_email,
    upload_avatar_pic,
    all_friends,
    request_friend,
    accept_or_decline_friend,
    request_friend_status,
    delete_friend,
)

router = APIRouter()


@router.get("/get_user/", response_model=UserData)
async def get_user(request: Request, db: AsyncSession = Depends(get_db)):
    return await get_user_with_email(request.state.user_email, db)


@router.post("/upload_avatar/", response_model=UserData)
async def upload_avatar(
    request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    return await upload_avatar_pic(request.state.user_email, file, db)


@router.get("/friendship/friends", response_model=List[UserData])
async def friends_all(request: Request, db: AsyncSession = Depends(get_db)):
    return await all_friends(request.state.user_email, "accepted", "outgoing", db)


@router.get("/friendship/friends/incoming", response_model=List[UserData])
async def friends_incoming(request: Request, db: AsyncSession = Depends(get_db)):
    return await all_friends(request.state.user_email, "requested", "incoming", db)


@router.post("/friendship/request", response_model=FriendshipData)
async def friend_request(
    request: Request, friend_id: int, db: AsyncSession = Depends(get_db)
):
    return await request_friend(request.state.user_email, friend_id, db)


@router.get("/friendship/request/status", response_model=FriendshipData)
async def friend_request_status(
    request: Request, friend_id: int, db: AsyncSession = Depends(get_db)
):
    return request_friend_status(request.state.user_email, friend_id, db)


@router.patch("/friendship/accept", response_model=FriendshipData)
async def friend_accept(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await accept_or_decline_friend(request.state.user_email, requested_id, "accept", db)


@router.patch("/friendship/decline", response_model=FriendshipData)
async def friend_decline(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await accept_or_decline_friend(request.state.user_email, requested_id, "decline", db)


@router.delete("/friendship/delete")
async def friend_delete(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    return await delete_friend(request.state.user_email, requested_id, db)
