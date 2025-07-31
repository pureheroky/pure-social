from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from .schemas import UserData, FriendshipData
from db.models.friendship import Friendship
from utils.db_utils import (
    execute_db_operation,
    get_user_by_id,
    require_user_by_email,
    validate_and_upload_image,
)
from utils.logger import setup_log
from core.config import get_settings
from utils.gcs_manager import GCSManager
from PIL import Image
import io

settings = get_settings()
logger = setup_log("users", __name__)
gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
ALLOWED_EXTENSIONS = {".jpg", ".png", ".webp"}


async def get_user_with_email(email: str, db: AsyncSession) -> UserData:
    logger.info(f"Trying to get user with email: {email}")
    user = await require_user_by_email(email, db, logger)

    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    return UserData.model_validate(user)


async def upload_avatar_pic(email: str, file: UploadFile, db: AsyncSession) -> UserData:
    logger.info(f"Trying to update profile picture of user with email: {email}")

    user = await require_user_by_email(email, db, logger)

    if user.profile_pic:
        old_blob_name = user.profile_pic.split(
            f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
        )[-1].split("?")[0]
        gcs_client.delete_file(old_blob_name)

    avatar_url = await validate_and_upload_image(
        db, file, ALLOWED_EXTENSIONS, gcs_client, logger, user.id, "avatars"
    )

    def operation():
        user.profile_pic = avatar_url
        return UserData.model_validate(user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully updated profile picture for user {email}",
        f"Error updating profile picture for user {email}",
        logger,
        refresh_object=user,
        use_flush=True,
    )

    # if not file.filename:
    #     logger.error(f"Unsupported file for user {email}")
    #     raise HTTPException(status_code=500, detail="Avatar was not properly provided")
    # file_ext = f".{file.filename.split(".")[-1].lower()}"
    # if file_ext not in ALLOWED_EXTENSIONS:
    #     logger.error(f"Unsupported file format for user {email}: {file.filename}")
    #     raise HTTPException(status_code=500, detail="Unsupported file format")
    # try:
    #     img = Image.open(io.BytesIO(await file.read()))
    #     img.verify()
    #     file.file.seek(0)

    #     if user.profile_pic:
    #         old_blob_name = user.profile_pic.split(
    #             f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
    #         )[-1].split("?")[0]
    #         gcs_client.delete_file(old_blob_name)

    #     user_id = user.id
    #     avatar_url = gcs_client.upload_file(file.file, file_ext, user_id, "avatars")

    #     user.profile_pic = avatar_url
    #     await db.commit()
    #     await db.refresh(user)
    #     logger.info(f"Successfully updated profile picture for user {email}")
    #     return UserData.model_validate(user)

    # except Image.UnidentifiedImageError:
    #     logger.error(f"Invalid image file for user: {email}")
    #     raise HTTPException(status_code=400, detail="Invalid image file")
    # except Exception as e:
    #     await db.rollback()
    #     logger.error(f"Error uploading profile picture for user {email}: {str(e)}")
    #     raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


async def request_friend_status(
    email: str, to_id: int, db: AsyncSession
) -> FriendshipData:
    logger.info(f"Trying to get friend request status from: {email} to: {to_id}")

    user = await require_user_by_email(email, db, logger)

    result = await db.execute(
        select(Friendship).filter(
            Friendship.user_id == user.id, Friendship.friend_id == to_id
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="Friendship was not found")

    return FriendshipData.model_validate(friendship)


async def request_friend(email: str, to_id: int, db: AsyncSession) -> FriendshipData:
    logger.info(f"Trying to send friend request from: {email} to: {to_id}")
    user = await require_user_by_email(email, db, logger)

    user_id = user.id
    if user_id == to_id:
        logger.error(f"User tried to send request to himself: {email}")
        raise HTTPException(
            status_code=400, detail=f"You can not send request to yourself"
        )

    if not await get_user_by_id(user_id, db) or not await get_user_by_id(to_id, db):
        logger.error(f"User with id {user_id} or {to_id} does not exist")
        raise HTTPException(
            status_code=404, detail=f"User with id {user_id} or {to_id} does not found"
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
                status_code=400, detail=f"User {to_id} is in friendlist already"
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

    return await execute_db_operation(
        db,
        lambda: (db.add(new_request), FriendshipData.model_validate(new_request))[-1],
        f"Successfully registered new friendship between: {user_id} and {to_id}",
        "Error while registering new friendship",
        logger,
        refresh_object=new_request,
    )


async def accept_or_decline_friend(
    email: str, from_id: int, action: str, db: AsyncSession
) -> FriendshipData:
    logger.info(f"Trying to update friend request status from: {from_id} to: {email}")

    user = await require_user_by_email(email, db, logger)

    user_id = user.id

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

    try:
        async with db.begin():
            friendship.status = new_status
            if new_status == "accepted":
                friendship.accepted_at = datetime.now(timezone.utc)
                reverse_friendship = Friendship(
                    user_id=user_id,
                    friend_id=from_id,
                    status=new_status,
                    requested_at=datetime.now(timezone.utc),
                    accepted_at=datetime.now(timezone.utc),
                )
                db.add(reverse_friendship)
                await db.refresh(reverse_friendship)
                logger.info(
                    f"Successfully confirmed new status for friendship between: {user_id} and {from_id}"
                )
                return FriendshipData.model_validate(reverse_friendship)
            else:
                await db.refresh(friendship)
                logger.info(
                    f"Friendship status updated to declined between: {user_id}-{email} and {from_id}"
                )
                return FriendshipData.model_validate(friendship)
    except Exception as e:
        logger.error(f"Error while confirming new status for friendship: {e}")
        raise HTTPException(
            status_code=500, detail="Error while confirming new status for friendship"
        )


async def all_friends(
    email: str, status_filter: str, direction: str, db: AsyncSession
) -> List[UserData]:
    logger.info(f"Trying to get friends of user with email: {email}")
    user = await require_user_by_email(email, db, logger)

    user_id = user.id

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
            .options(selectinload(Friendship.user))
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


async def delete_friend(email: str, friend_id: int, db: AsyncSession) -> dict:
    logger.info(f"Trying to delete friendship between {email} and {friend_id}")

    user = await require_user_by_email(email, db, logger)

    user_id = user.id

    if not await get_user_by_id(user_id, db) or not await get_user_by_id(friend_id, db):
        logger.error(f"User {user_id}-{email} or friend {friend_id} was not found")
        raise HTTPException(status_code=404, detail="User or friend was not found")

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

    return await execute_db_operation(
        db,
        lambda: (
            db.delete(friendship),
            db.delete(reverse_friendship),
            {"detail": "Friendship deleted", "status_code": 200},
        )[-1],
        f"Friendship between {user_id} and {friend_id} successfully deleted",
        f"Error while deleting friendship between {user_id} and {friend_id}",
        logger,
    )
