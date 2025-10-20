from typing import List
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.friendship import FriendshipStatus
from db.session import get_db
from ..schemas import FriendshipData, UserData
from ..services import (
    get_user_by_id,
    get_user_with_email,
    upload_avatar_pic,
    all_friends,
    request_friend,
    accept_or_decline_friend,
    request_friend_status,
    delete_friend,
    block_user,
    unblock_user,
)

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status":"ok"}

@router.get("/me", response_model=UserData)
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user from by email from state."""
    return await get_user_with_email(request.state.user_email, db)


@router.get("/get_user/id", response_model=UserData)
async def get_user_id(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user by ID."""
    return await get_user_by_id(user_id, db)


@router.post("/upload_avatar/", response_model=UserData, status_code=201)
async def upload_avatar(
    request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Upload avatar."""
    return await upload_avatar_pic(request.state.user_email, file, db)


@router.get("/friends", response_model=List[UserData])
async def friends_all(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get all friends (ACCEPTED)."""
    return await all_friends(
        request.state.user_email,
        FriendshipStatus.ACCEPTED,
        "outgoing",
        db,
        limit,
        offset,
    )


@router.get("/friends/requests/incoming", response_model=List[UserData])
async def friends_incoming(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get incoming friend requests (PENDING)."""
    return await all_friends(
        request.state.user_email,
        FriendshipStatus.PENDING,
        "incoming",
        db,
        limit,
        offset,
    )


@router.post("/friendship/request", response_model=FriendshipData, status_code=201)
async def friend_request(
    request: Request, friend_id: int, db: AsyncSession = Depends(get_db)
):
    """Send a friend request."""
    return await request_friend(request.state.user_email, friend_id, db)


@router.get("/friendship/request/status", response_model=FriendshipData)
async def friend_request_status(
    request: Request, friend_id: int, db: AsyncSession = Depends(get_db)
):
    """Get status of friend request."""
    return await request_friend_status(request.state.user_email, friend_id, db)


@router.patch("/friendship/accept", response_model=FriendshipData)
async def friend_accept(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    """Accept friend request."""
    return await accept_or_decline_friend(
        request.state.user_email, requested_id, "accept", db
    )


@router.patch("/friendship/decline", response_model=FriendshipData)
async def friend_decline(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    """Decline friend request."""
    return await accept_or_decline_friend(
        request.state.user_email, requested_id, "decline", db
    )


@router.delete("/friendship/delete")
async def friend_delete(
    request: Request, requested_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete friendship."""
    return await delete_friend(request.state.user_email, requested_id, db)


@router.post("/block_user", response_model=FriendshipData, status_code=201)
async def block_user_endpoint(
    request: Request, user_id: int, db: AsyncSession = Depends(get_db)
):
    """Block user."""
    return await block_user(request.state.user_email, user_id, db)


@router.post("/unblock_user", response_model=FriendshipData, status_code=201)
async def unblock_user_endpoint(
    request: Request, user_id: int, db: AsyncSession = Depends(get_db)
):
    """Unblock user."""
    return await unblock_user(request.state.user_email, user_id, db)
