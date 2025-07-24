from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.post import Post
from db.models.post_reaction import PostReaction
from .schemas import PostData, PostReactionData
from utils.logger import setup_log
from utils.db_utils import get_user_by_email
from utils.gcs_manager import GCSManager
from core.config import get_settings
from PIL import Image
import io

logger = setup_log("posts", __name__)
settings = get_settings()
gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
ALLOWED_EXTENSIONS = {".jpg", ".png", ".webp"}


# TODO: Reformat all code duplicates


async def get_posts(email: str, db: AsyncSession) -> List[PostData]:
    logger.info(f"Trying to get posts of user: {email}")
    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(author_id=user.id))
    posts = result.scalars().all()

    if not posts:
        logger.info(f"User {email} doesn't have any post")

    return [PostData.model_validate(post) for post in posts]


async def create_post(
    email: str,
    post_text: str,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    logger.info(f"User {email} creating post")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    post_image_url = None

    if post_image:
        if not post_image.filename:
            logger.error(f"Unsupported file for user {email}")
            raise HTTPException(
                status_code=500, detail="Image was not properly provided"
            )
        file_ext = f".{post_image.filename.split(".")[-1].lower()}"
        if file_ext not in ALLOWED_EXTENSIONS:
            logger.error(
                f"Unsupported file format for user {email}: {post_image.filename}"
            )
            raise HTTPException(status_code=500, detail="Unsupported file format")
        try:
            img = Image.open(io.BytesIO(await post_image.read()))
            img.verify()
            post_image.file.seek(0)

            post_image_url = gcs_client.upload_file(
                post_image.file, file_ext, user.id, "posts"
            )
            logger.info(f"Image uploaded to GCS for user {email}: {post_image_url}")

        except Image.UnidentifiedImageError:
            logger.error(f"Invalid post image file for user: {email}")
            raise HTTPException(status_code=400, detail="Invalid post image file")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error uploading post picture for user {email}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error uploading post image file: {str(e)}"
            )

    new_post = Post(
        author_id=user.id,
        post_text=post_text,
        post_image=post_image_url,
        post_likes=0,
    )

    try:
        db.add(new_post)
        await db.commit()
        await db.refresh(new_post)
        logger.info(f"Successfully created new post for {user.email}")
        return PostData.model_validate(new_post)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while creating new post for {user.email}")
        raise HTTPException(
            status_code=500, detail=f"Error while creating new post: {e}"
        )


async def delete_post(email: str, post_id: int, db: AsyncSession) -> dict:
    logger.info(f"User {email} deleting post: {post_id}")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(id=post_id))
    post = result.scalar_one_or_none()

    if post is None:
        logger.error(f"User's {email} post {post_id} was not found")
        raise HTTPException(status_code=400, detail="User's post was not found")

    try:
        await db.delete(post)
        await db.commit()
        logger.info(f"Post {post_id} was successfully deleted")
        return {"detail": "Post was successfully deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while deleting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Error while deleting post")


async def edit_post(
    email: str,
    post_text: str | None,
    post_id: str,
    remove_image: bool,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    logger.info(f"User {email} editing post: {post_id}")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(id=post_id))
    post = result.scalar_one_or_none()

    if post is None:
        logger.error(f"User's {email} post {post_id} was not found")
        raise HTTPException(status_code=400, detail="User's post was not found")

    if post_text is not None:
        post.post_text = post_text

    if remove_image:
        if post.post_image:
            old_blob_name = post.post_image.split(
                f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
            )[-1].split("?")[0]
            gcs_client.delete_file(old_blob_name)
            post.post_image = None

    elif post_image is not None:
        if not post_image.filename:
            logger.error(f"Unsupported file for user {email}")
            raise HTTPException(
                status_code=500, detail="Image was not properly provided"
            )

        file_ext = f".{post_image.filename.split(".")[-1].lower()}"
        if file_ext not in ALLOWED_EXTENSIONS:
            logger.error(
                f"Unsupported file format for user {email}: {post_image.filename}"
            )
            raise HTTPException(status_code=500, detail="Unsupported file format")

        url = gcs_client.upload_file(post_image.file, file_ext, user.id, "posts")
        post.post_image = url

    post.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
        await db.refresh(post)
        logger.info(f"Post {post_id} was successfully edited")
        return PostData.model_validate(post)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while editing post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Error while editing post")


async def reacted_post(email: str, db: AsyncSession) -> List[PostData]:
    logger.info(f"Trying to get user {email} reactions")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    try:
        query = (
            select(Post)
            .join(PostReaction, Post.id == PostReaction.post_id)
            .filter(PostReaction.user_id == user.id)
        )
        result = await db.execute(query)
        posts = result.scalars().all()

        if not posts:
            logger.info(f"No reacted posts found for user {email}")
            return []

        posts_data_list = [PostData.model_validate(post) for post in posts]
        logger.info(
            f"Successfully retrieved {len(posts_data_list)} reacted posts for {email}"
        )
        return posts_data_list
    except Exception as e:
        logger.error(f"Error while retrieving reacted posts for {email}: {e}")
        raise HTTPException(status_code=500, detail="Error while retrieving posts")


async def like_post(email: str, post_id: int, db: AsyncSession) -> dict:
    logger.info(f"User {email} liked post {post_id}")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(id=post_id))
    post = result.scalar_one_or_none()

    if post is None:
        logger.error(f"Post {post_id} was not found")
        raise HTTPException(status_code=400, detail="Post was not found")

    existing_reaction = await db.execute(
        select(PostReaction).filter_by(
            post_id=post_id, user_id=user.id, reaction_type="like"
        )
    )

    if existing_reaction.scalar_one_or_none():
        logger.info(f"User {email} already liked post {post_id}")
        return {"message": "Already liked post", "status_code": 400}

    try:
        post.post_likes += 1

        new_reaction = PostReaction(
            post_id=post_id,
            user_id=user.id,
            reaction_type="like",
            created_at=datetime.now(timezone.utc),
        )

        db.add(new_reaction)
        await db.commit()
        await db.refresh(new_reaction)
        logger.info(f"User {email} liked post {post_id}")
        return {"message": "Post liked successfully", "status_code": 200}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while adding like to post {post_id} from {user}: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong")


async def dislike_post(email: str, post_id: int, db: AsyncSession) -> dict:
    logger.info(f"User {email} disliked post {post_id}")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(id=post_id))
    post = result.scalar_one_or_none()

    if post is None:
        logger.error(f"Post {post_id} was not found")
        raise HTTPException(status_code=400, detail="Post was not found")

    result = await db.execute(
        select(PostReaction).filter_by(
            post_id=post_id, user_id=user.id, reaction_type="like"
        )
    )

    reaction = result.scalar_one_or_none()

    if reaction is None:
        logger.info(f"User {email} has not liked post {post_id}")
        return {"message": "Not liked post", "status_code": 400}

    try:
        if post.post_likes > 0:
            post.post_likes -= 1
        else:
            logger.error(f"Trying to decrease less than zero post {post_id}")

        await db.delete(reaction)

        await db.commit()
        await db.refresh(post)
        logger.info(f"User {email} disliked post {post_id}")
        return {"message": "Post disliked successfully", "status_code": 200}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error while adding dislike to post {post_id} from {user}: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong")
