from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.engine import result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from .schemas import UserData, FriendshipData
from db.models.user import Friendship, User
from utils.db_utils import check_user_exists
from utils.logger import setup_log
import logging
from core.config import get_settings
from utils.gcs_manager import GCSManager
from PIL import Image
import io

settings = get_settings()
setup_log("auth")
logger = logging.getLogger(__name__)

gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
ALLOWED_EXTENSIONS = {".jpg", ".png", ".png", ".webp"}


async def get_user_by_id(user_id: int, db: AsyncSession) -> UserData:
    logger.info(f"Trying to get user with id: {user_id}")
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"User with id {user_id} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    return UserData.model_validate(user)


async def upload_avatar_pic(
    user_id: int, file: UploadFile, db: AsyncSession
) -> UserData:
    logger.info(f"Trying to update profile picture of user with id: {user_id}")

    if not file.filename:
        logger.error(f"Unsupported file for user {user_id}")
        raise HTTPException(status_code=500, detail="Avatar was not properly provided")

    file_ext = f".{file.filename.split(".")[-1].lower()}"
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.error(f"Unsupported file format for user {user_id}: {file.filename}")
        raise HTTPException(status_code=500, detail="Unsupported file format")

    try:
        img = Image.open(io.BytesIO(await file.read()))
        img.verify()
        file.file.seek(0)
        avatar_url = gcs_client.upload_file(file.file, file_ext, user_id, "avatars")
        result = await db.execute(select(User).filter_by(id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.error(f"User with id {user_id} was not found during avatar update")
            raise HTTPException(status_code=500, detail="User was not found")

        if user.profile_pic:
            old_blob_name = user.profile_pic.split(
                f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
            )[-1].split("?")[0]
            gcs_client.delete_file(old_blob_name)

        user.profile_pic = avatar_url
        await db.commit()

        logger.info(f"Successfully updated profile picture for user {user_id}")
        return UserData.model_validate(user)

    except Image.UnidentifiedImageError:
        logger.error(f"Invalid image file for user: {user_id}")
        raise HTTPException(status_code=400, detail="Invalid image file")
    except Exception as e:
        logger.error(f"Error uploading profile picture for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


async def request_friend_status(
    user_id: int, to_id: int, db: AsyncSession
) -> FriendshipData:
    logger.info(f"Trying to get friend request status from: {user_id} to: {to_id}")
    result = await db.execute(
        select(Friendship).filter(
            Friendship.user_id == user_id, Friendship.friend_id == to_id
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship was not found")

    return FriendshipData.model_validate(friendship)


async def request_friend(user_id: int, to_id: int, db: AsyncSession) -> FriendshipData:
    logger.info(f"Trying to send friend request from: {user_id} to: {to_id}")
    if user_id == to_id:
        logger.error(f"User tried to send request to himself: {user_id}")
        raise HTTPException(
            status_code=400, detail=f"You can not send request to yourself"
        )

    if not await check_user_exists(user_id, db) or not await check_user_exists(
        to_id, db
    ):
        logger.error(f"User with id {user_id} or {to_id} does not exist")
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} or {to_id} d not found"
        )

    existing = await db.execute(
        select(Friendship).filter(
            and_(Friendship.user_id == user_id, Friendship.friend_id == to_id)
        )
    )

    existing_request = existing.scalar_one_or_none()

    if existing_request:
        if existing_request.status == "accepted":
            logger.error(f"Users are friends already: {user_id} - {to_id}")
            raise HTTPException(
                status_code=400, detail=f"{to_id} is in friendlist already"
            )
        elif existing_request.status == "requested":
            logger.error(f"Friend request already sent: {user_id} - {to_id}")
            raise HTTPException(
                status_code=400, detail=f"Request to {to_id} already sent"
            )
        elif existing_request.status == "declined":
            logger.error(f"Friend request was declined: {user_id} - {to_id}")
            raise HTTPException(status_code=400, detail=f"Friend request was declined")

    new_request = Friendship(
        user_id=user_id,
        friend_id=to_id,
        status="requested",
        requested_at=datetime.now(timezone.utc),
        accepted_at=None,
    )

    try:
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        logger.info(
            f"Successfully registered new friendship between: {user_id} and {to_id}"
        )
        return FriendshipData.model_validate(new_request)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while registering new friendship: {e}")
        raise HTTPException(
            status_code=500, detail="Error while creating new friendship"
        )


async def accept_or_decline_friend(
    user_id: int, from_id: int, action: str, db: AsyncSession
) -> FriendshipData:
    logger.info(f"Trying to update friend request status from: {from_id} to: {user_id}")
    request_to_accept = await db.execute(
        select(Friendship).filter(
            Friendship.user_id == from_id,
            Friendship.friend_id == user_id,
            Friendship.status == "requested",
        )
    )

    friendship = request_to_accept.scalar_one_or_none()
    if not friendship:
        logger.error(f"Friend request of users {user_id} and {from_id} does not exists")
        raise HTTPException(status_code=404, detail="Friend request does not exists")

    new_status = "accepted" if action == "accept" else "declined"

    friendship.status = new_status
    if new_status == "accepted":
        friendship.accepted_at = datetime.now(timezone.utc)
    await db.commit()

    if new_status == "declined":
        return FriendshipData.model_validate(friendship)

    reverse_friendship = Friendship(
        user_id=user_id,
        friend_id=from_id,
        status=new_status,
        requested_at=datetime.now(timezone.utc),
        accepted_at=datetime.now(timezone.utc),
    )

    try:
        db.add(reverse_friendship)
        await db.commit()
        await db.refresh(reverse_friendship)
        logger.info(
            f"Successfully confirmed new status for friendship between: {user_id} and {from_id}"
        )
        return FriendshipData.model_validate(reverse_friendship)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while confirming new status for friendship: {e}")
        raise HTTPException(
            status_code=500, detail="Error while confirming new status for friendship"
        )


async def all_friends(
    user_id: int, status_filter: str, direction: str, db: AsyncSession
) -> List[UserData]:
    logger.info(f"Trying to get friends of user with id: {user_id}")
    if not await check_user_exists(user_id, db):
        raise HTTPException(status_code=404, detail="User does not exists")

    if direction == "outgoing":
        query = (
            select(Friendship)
            .filter(
                and_(Friendship.user_id == user_id, Friendship.status == status_filter)
            )
            .options(selectinload(Friendship.friend))
        )
    elif direction == "incoming":
        query = (
            select(Friendship)
            .filter(
                and_(
                    Friendship.friend_id == user_id, Friendship.status == status_filter
                )
            )
            .options(selectinload(Friendship.friend))
        )
    else:
        logger.error(
            f"Wrong direction on attempt to get friends status with direction: {direction}"
        )
        raise HTTPException(status_code=400, detail="Wrong direction")

    result = await db.execute(query)
    friendships = result.scalars().all()

    if direction == "outgoing":
        users = [friendship.friend for friendship in friendships]
    else:
        users = [friendship.user for friendship in friendships]

    return [UserData.model_validate(user) for user in users]


async def delete_friend(user_id: int, friend_id: int, db: AsyncSession) -> dict:
    logger.info(f"Trying to delete friendship between {user_id} and {friend_id}")

    if not await check_user_exists(user_id, db) or not await check_user_exists(
        friend_id, db
    ):
        raise HTTPException(status_code=404)

    result = await db.execute(
        select(Friendship)
        .filter(
            and_(
                Friendship.user_id == user_id,
                Friendship.friend_id == friend_id,
                Friendship.status == "accepted",
            )
        )
        .options(selectinload(Friendship.friend))
    )

    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship was not found")

    reverse_result = await db.execute(
        select(Friendship)
        .filter(
            and_(
                Friendship.user_id == friend_id,
                Friendship.friend_id == user_id,
                Friendship.status == "accepted",
            )
        )
        .options(selectinload(Friendship.friend))
    )

    reverse_friendship = reverse_result.scalar_one_or_none()
    if not reverse_friendship:
        raise HTTPException(status_code=404, detail="Reverse friendship was not found")

    try:
        await db.delete(friendship)
        await db.delete(reverse_friendship)
        await db.commit()
        logger.info(
            f"Friendship between {user_id} and {friend_id} successfully deleted"
        )
        return {"detail": "Friendship deleted"}
    except:
        logger.error(
            f"Error while deleting friendship between {user_id} and {friend_id}"
        )
        raise HTTPException(status_code=500, detail="Error while deleting friendship")
