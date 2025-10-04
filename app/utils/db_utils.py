from logging import Logger
from typing import Callable, Optional, TypeVar, Any, Awaitable, cast
from utils.gcs_manager import GCSManager
from db.models.post import Post
from db.models.user import User
from db.models.comment import Comment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, UploadFile
from PIL import Image
import io
import asyncio


T = TypeVar("T")


async def require_user_by_id(user_id: int, db: AsyncSession, logger: Logger) -> User | None:
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.error(f"User with id {user_id} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    return user


async def require_comment_author(
    comment_id: int, user_id: int, db: AsyncSession, logger: Logger
) -> Comment:
    """Require the user to be the author of the comment."""
    result = await db.execute(select(Comment).filter_by(id=comment_id))
    comment = result.scalar_one_or_none()

    if comment is None:
        logger.error(f"Comment {comment_id} was not found")
        raise HTTPException(status_code=400, detail="Comment was not found")

    if comment.user_id != user_id:
        logger.error(
            f"User {user_id} cannot delete comment {comment_id} (author: {comment.user_id})"
        )
        raise HTTPException(
            status_code=400, detail="User is not the author of the comment"
        )

    return comment


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    user_req = await db.execute(select(User).filter_by(email=email))
    return user_req.scalar_one_or_none()


async def require_user_by_email(email: str, db: AsyncSession, logger: Logger) -> User:
    user_req = await db.execute(select(User).filter_by(email=email))
    user = user_req.scalar_one_or_none()

    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    return user


async def require_post_author(
    post_id: int, user_id: int, db: AsyncSession, logger: Logger
) -> Post:
    post = await db.execute(select(Post).filter_by(id=post_id))
    post = post.scalar_one_or_none()

    if post is None:
        logger.error(f"User's {user_id} post {post_id} was not found")
        raise HTTPException(status_code=400, detail="User's post was not found")

    if post.author_id != user_id:
        logger.error(f"User {user_id} can not delete post {post.author_id}")
        raise HTTPException(status_code=400, detail="User is not creator of post")

    return post


async def validate_and_upload_image(
    db: AsyncSession,
    file: UploadFile,
    allowed_extensions: set,
    gcs_client: GCSManager,
    logger: Logger,
    user_id: int,
    folder: str,
) -> str:
    if not file.filename:
        logger.error(f"Unsupported file for user {user_id}")
        raise HTTPException(status_code=500, detail="Avatar was not properly provided")

    file_ext = f".{file.filename.split(".")[-1].lower()}"
    if file_ext not in allowed_extensions:
        logger.error(f"Unsupported file format for user {user_id}: {file.filename}")
        raise HTTPException(status_code=500, detail="Unsupported file format")

    try:
        img = Image.open(io.BytesIO(await file.read()))
        img.verify()
        file.file.seek(0)
        image_url = gcs_client.upload_file(file.file, file_ext, user_id, folder)
        return image_url
    except Image.UnidentifiedImageError:
        logger.error(f"Invalid image file for user: {user_id}")
        raise HTTPException(status_code=400, detail="Invalid image file")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error uploading profile picture for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


async def execute_db_operation(
    db: AsyncSession,
    operation: Callable[[], T] | Callable[[], Awaitable[T]],
    success_message: str,
    error_message: str,
    logger: Logger,
    status_code: int = 500,
    refresh_object: Optional[Any] = None,
    use_flush: bool = False,
) -> T:
    try:
        result = operation()
        if asyncio.iscoroutine(result):
            result = await result
        result = cast(T, result)
        if use_flush:
            await db.flush()
        if refresh_object:
            await db.refresh(refresh_object)
        await db.commit()
        logger.info(success_message)
        return result
    except Exception as e:
        await db.rollback()
        logger.error(f"{error_message}: {str(e)}")
        raise HTTPException(status_code=status_code, detail=error_message)
