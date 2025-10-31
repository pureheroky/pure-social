from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, and_
from sqlalchemy.orm import selectinload
from .schemas import UserData, FriendshipData
from db.models.friendship import Friendship, FriendshipStatus
from utils.db_utils import (
    execute_db_operation,
    require_user_by_email,
    require_user_by_id,
    validate_and_upload_image,
)
from utils.logger import setup_log
from core.config import get_settings
from utils.gcs_manager import GCSManager

settings = get_settings()
logger = setup_log("users", __name__)
gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
ALLOWED_EXTENSIONS = {".jpg", ".png", ".webp", ".jpeg"}


async def get_user_with_email(email: str, db: AsyncSession) -> UserData:
    """Get user by email."""
    logger.info(f"Trying to get user with id from email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    return UserData.model_validate(user)


async def get_user_by_id(user_id: int, db: AsyncSession) -> UserData:
    """Get user by ID."""
    logger.info(f"Trying to get user with id: {user_id}")
    user = await require_user_by_id(user_id, db, logger)
    return UserData.model_validate(user)


async def upload_avatar_pic(email: str, file: UploadFile, db: AsyncSession) -> UserData:
    """Upload/Update user avatar."""
    logger.info(f"Trying to update profile picture for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    if user.profile_pic:
        parsed_url = urlparse(user.profile_pic)
        old_blob_name = parsed_url.path.lstrip("/")

        bucket_prefix = f"{gcs_client.bucket_name()}/"
        if old_blob_name.startswith(bucket_prefix):
            old_blob_name = old_blob_name[len(bucket_prefix):]

        if "?" in old_blob_name:
            old_blob_name = old_blob_name.split("?")[0]

        gcs_client.delete_file(old_blob_name)

    avatar_url = await validate_and_upload_image(
        db, file, ALLOWED_EXTENSIONS, gcs_client, logger, user.id, "avatars"
    )

    async def operation() -> UserData:
        user.profile_pic = avatar_url
        await db.flush()
        await db.refresh(user)
        return UserData.model_validate(user)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully updated profile picture for user {user.id}",
        f"Error updating profile picture for user {user.id}",
        logger,
        refresh_object=user,
        use_flush=True,
    )


async def request_friend_status(
    email: str, to_id: int, db: AsyncSession
) -> FriendshipData:
    """Get friendship status."""
    logger.info(
        f"Trying to get friend request status from user email: {email[:5]}... to id: {to_id}"
    )
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
    """Send a friend request."""
    user = await require_user_by_email(email, db, logger)
    if user.id == to_id:
        raise HTTPException(400, detail="Cannot request yourself")

    existing_block = await db.execute(
        select(Friendship).filter(
            or_(
                and_(
                    Friendship.user_id == user.id,
                    Friendship.friend_id == to_id,
                    Friendship.status == FriendshipStatus.BLOCKED,
                ),
                and_(
                    Friendship.user_id == to_id,
                    Friendship.friend_id == user.id,
                    Friendship.status == FriendshipStatus.BLOCKED,
                ),
            )
        )
    )
    if existing_block.scalar_one_or_none():
        raise HTTPException(400, detail="User is blocked")

    existing = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.user_id == user.id, Friendship.friend_id == to_id),
                and_(Friendship.user_id == to_id, Friendship.friend_id == user.id),
            )
        )
    )
    existing = existing.scalar_one_or_none()

    if existing:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(400, detail="Already friends")
        elif existing.status == FriendshipStatus.PENDING:
            raise HTTPException(400, detail="Request already sent")

    new_request = Friendship(
        user_id=user.id,
        friend_id=to_id,
        status=FriendshipStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
        accepted_at=None,
    )

    async def operation() -> FriendshipData:
        db.add(new_request)
        await db.flush()
        await db.refresh(new_request)
        return FriendshipData.model_validate(new_request)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully registered new friendship between: {user.id} and {to_id}",
        "Error while registering new friendship",
        logger,
    )


async def accept_or_decline_friend(
    email: str, from_id: int, action: str, db: AsyncSession
) -> FriendshipData:
    """Accept/Decline friend request."""
    logger.info(
        f"Trying to update friend request status from id: {from_id} for user email: {email[:5]}..."
    )
    user = await require_user_by_email(email, db, logger)
    user_id = user.id

    result = await db.execute(
        select(Friendship).filter(
            Friendship.user_id == from_id,
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship:
        logger.error(f"Friend request between {user_id} and {from_id} does not exist")
        raise HTTPException(status_code=404, detail="Friend request does not exist")

    new_status = (
        FriendshipStatus.ACCEPTED if action == "accept" else FriendshipStatus.REJECTED
    )

    async def operation() -> FriendshipData:
        friendship.status = new_status
        if new_status == FriendshipStatus.ACCEPTED:
            friendship.accepted_at = datetime.now(timezone.utc)
            reverse_friendship = Friendship(
                user_id=user_id,
                friend_id=from_id,
                status=new_status,
                requested_at=friendship.requested_at,
                accepted_at=datetime.now(timezone.utc),
            )
            db.add(reverse_friendship)
            await db.flush()
            await db.refresh(friendship)
            await db.refresh(reverse_friendship)
        else:
            await db.flush()
            await db.refresh(friendship)
        return FriendshipData.model_validate(friendship)

    success_msg = (
        f"Successfully updated friendship status between: {user_id} and {from_id}"
    )
    error_msg = f"Error updating friendship status between: {user_id} and {from_id}"

    return await execute_db_operation(
        db,
        operation,
        success_msg,
        error_msg,
        logger,
        refresh_object=friendship,
    )


async def all_friends(
    email: str,
    status_filter: FriendshipStatus,
    direction: str,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> List[UserData]:
    """Get list of friends/requests (outgoing/incoming)."""
    logger.info(f"Trying to get friends for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    user_id = user.id

    if direction == "outgoing":
        query = (
            select(Friendship)
            .filter(
                and_(Friendship.user_id == user_id, Friendship.status == status_filter)
            )
            .options(selectinload(Friendship.friend))
            .limit(limit)
            .offset(offset)
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
            .limit(limit)
            .offset(offset)
        )
    else:
        raise HTTPException(
            status_code=400, detail="Direction must be 'outgoing' or 'incoming'"
        )

    result = await db.execute(query)
    friendships = result.scalars().all()

    if direction == "outgoing":
        users = [friendship.friend for friendship in friendships]
    else:
        users = [friendship.user for friendship in friendships]

    return [UserData.model_validate(u) for u in users]


async def delete_friend(email: str, friend_id: int, db: AsyncSession) -> FriendshipData:
    """Delete friendship (ACCEPTED or PENDING)."""
    logger.info(
        f"Trying to delete friendship for user email: {email[:5]}... and id: {friend_id}"
    )
    user = await require_user_by_email(email, db, logger)
    await require_user_by_id(friend_id, db, logger)

    if user.id == friend_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    async def operation() -> FriendshipData:
        result = await db.execute(
            select(Friendship).filter(
                and_(
                    Friendship.user_id == user.id,
                    Friendship.friend_id == friend_id,
                    or_(
                        Friendship.status == FriendshipStatus.ACCEPTED,
                        Friendship.status == FriendshipStatus.PENDING,
                    ),
                )
            )
        )
        friendship = result.scalar_one_or_none()
        if not friendship:
            raise HTTPException(status_code=404, detail="Friendship was not found")

        if friendship.status == FriendshipStatus.ACCEPTED:
            reverse_result = await db.execute(
                select(Friendship).filter(
                    and_(
                        Friendship.user_id == friend_id,
                        Friendship.friend_id == user.id,
                        Friendship.status == FriendshipStatus.ACCEPTED,
                    )
                )
            )
            reverse_friendship = reverse_result.scalar_one_or_none()
            if reverse_friendship:
                db.delete(reverse_friendship)

        db.delete(friendship)
        await db.flush()
        await db.refresh(friendship)
        return FriendshipData.model_validate(friendship)

    return await execute_db_operation(
        db,
        operation,
        f"Friendship between {user.id} and {friend_id} successfully deleted",
        f"Error deleting friendship between {user.id} and {friend_id}",
        logger,
    )


async def block_user(email: str, to_id: int, db: AsyncSession) -> FriendshipData:
    """Заблокировать пользователя."""
    logger.info(f"Trying to block user id: {to_id} by user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    if user.id == to_id:
        raise HTTPException(400, detail="Cannot block yourself")

    await require_user_by_id(to_id, db, logger)

    existing_result = await db.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.user_id == user.id, Friendship.friend_id == to_id),
                and_(Friendship.user_id == to_id, Friendship.friend_id == user.id),
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    async def operation() -> FriendshipData:
        if existing:
            if existing.status == FriendshipStatus.BLOCKED:
                raise HTTPException(400, detail="User already blocked")

            reverse_result = await db.execute(
                select(Friendship).filter(
                    and_(Friendship.user_id == to_id, Friendship.friend_id == user.id)
                )
            )
            reverse = reverse_result.scalar_one_or_none()
            if reverse:
                reverse.status = FriendshipStatus.BLOCKED
                await db.refresh(reverse)

            existing.status = FriendshipStatus.BLOCKED
            await db.flush()
            await db.refresh(existing)
            return FriendshipData.model_validate(existing)
        else:
            new_block = Friendship(
                user_id=user.id,
                friend_id=to_id,
                status=FriendshipStatus.BLOCKED,
                requested_at=datetime.now(timezone.utc),
                accepted_at=None,
            )
            db.add(new_block)
            await db.flush()
            await db.refresh(new_block)
            return FriendshipData.model_validate(new_block)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully blocked user {to_id} by user {user.id}",
        f"Error blocking user {to_id} by user {user.id}",
        logger,
        use_flush=True,
    )


async def unblock_user(email: str, to_id: int, db: AsyncSession) -> FriendshipData:
    """Unblock user."""
    logger.info(f"Trying to unblock user id: {to_id} by user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    if user.id == to_id:
        raise HTTPException(400, detail="Cannot unblock yourself")

    await require_user_by_id(to_id, db, logger)

    direct_result = await db.execute(
        select(Friendship).filter(
            and_(
                Friendship.user_id == user.id,
                Friendship.friend_id == to_id,
                Friendship.status == FriendshipStatus.BLOCKED,
            )
        )
    )
    direct = direct_result.scalar_one_or_none()

    if not direct:
        raise HTTPException(400, detail="User is not blocked")

    reverse_result = await db.execute(
        select(Friendship).filter(
            and_(
                Friendship.user_id == to_id,
                Friendship.friend_id == user.id,
                Friendship.status == FriendshipStatus.BLOCKED,
            )
        )
    )
    reverse = reverse_result.scalar_one_or_none()
    if reverse:
        db.delete(reverse)

    async def operation() -> FriendshipData:
        db.delete(direct)
        await db.flush()
        await db.refresh(direct)
        return FriendshipData.model_validate(direct)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully unblocked user {to_id} by user {user.id}",
        f"Error unblocking user {to_id} by user {user.id}",
        logger,
    )
