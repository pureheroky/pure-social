from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.post import Post
from db.models.post_reaction import PostReaction
from .schemas import PostData
from utils.logger import setup_log
from utils.db_utils import (
    execute_db_operation,
    require_post_author,
    require_user_by_email,
    validate_and_upload_image,
)
from utils.gcs_manager import GCSManager
from core.config import get_settings

logger = setup_log("posts", __name__)
settings = get_settings()
gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
ALLOWED_EXTENSIONS = {".jpg", ".png", ".webp"}


async def get_posts(email: str, db: AsyncSession) -> List[PostData]:
    logger.info(f"Trying to get posts of user: {email}")
    user = await require_user_by_email(email, db, logger)

    result = await db.execute(select(Post).filter_by(author_id=user.id))
    posts = result.scalars().all()

    if not posts:
        logger.info(f"User {email} doesn't have any post")
        return []

    return [PostData.model_validate(post) for post in posts]


async def create_post(
    email: str,
    post_text: str,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    logger.info(f"User {email} creating post")

    user = await require_user_by_email(email, db, logger)
    post_image_url = None

    if post_image:
        post_image_url = await validate_and_upload_image(
            db, post_image, ALLOWED_EXTENSIONS, gcs_client, logger, user.id, "posts"
        )

    new_post = Post(
        author_id=user.id,
        post_text=post_text,
        post_image=post_image_url,
        post_likes=0,
    )

    await execute_db_operation(
        db,
        lambda: db.add(new_post),
        f"Successfully created new post for {user.email}",
        f"Error while creating new post for {user.email}",
        logger,
        refresh_object=new_post,
        use_flush=True,
    )

    return PostData.model_validate(new_post)


async def delete_post(email: str, post_id: int, db: AsyncSession) -> dict:
    logger.info(f"User {email} deleting post: {post_id}")
    user = await require_user_by_email(email, db, logger)
    post = await require_post_author(post_id, user.id, db, logger)

    async def operation():
        await db.delete(post)
        return {"detail": "Post was successfully deleted"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully deleted post for {user.email}",
        f"Error while deleting post for {user.email}",
        logger,
    )


async def edit_post(
    email: str,
    post_text: str | None,
    post_id: str,
    remove_image: str,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    logger.info(f"User {email} editing post: {post_id}")

    user = await require_user_by_email(email, db, logger)
    post = await require_post_author(int(post_id), user.id, db, logger)

    if post_text is not None:
        post.post_text = post_text

    if remove_image == "true":
        if post.post_image:
            old_blob_name = post.post_image.split(
                f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
            )[-1].split("?")[0]
            try:
                blob = gcs_client.check_file_exist(
                    settings.GCS_BUCKET_NAME, old_blob_name
                )
                if blob:
                    gcs_client.delete_file(old_blob_name)
                    logger.debug(f"Deleted GCS file: {old_blob_name}")
                else:
                    logger.warning(f"GCS file not found: {old_blob_name}")
                post.post_image = None
            except Exception as e:
                logger.error(f"Failed to delete GCS file {old_blob_name}: {str(e)}")
                post.post_image = None

    elif post_image is not None:
        post_image_url = await validate_and_upload_image(
            db, post_image, ALLOWED_EXTENSIONS, gcs_client, logger, user.id, "posts"
        )
        post.post_image = post_image_url

    post.updated_at = datetime.now(timezone.utc)

    return await execute_db_operation(
        db,
        lambda: PostData.model_validate(post),
        f"Post {post_id} was successfully edited",
        f"Error while editing post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def reacted_post(email: str, db: AsyncSession) -> List[PostData]:
    logger.info(f"Trying to get user {email} reactions")
    user = await require_user_by_email(email, db, logger)

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
    user = await require_user_by_email(email, db, logger)
    post = await db.execute(select(Post).filter_by(id=post_id))
    post = post.scalar_one_or_none()

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

    post.post_likes += 1

    new_reaction = PostReaction(
        post_id=post_id,
        user_id=user.id,
        reaction_type="like",
        created_at=datetime.now(timezone.utc),
    )

    return await execute_db_operation(
        db,
        lambda: (
            db.add(new_reaction),
            {"message": "Post liked successfully", "status_code": 200},
        )[-1],
        f"User {email} liked post {post_id}",
        f"Error while adding like to post {post_id} from {user}",
        logger,
        refresh_object=new_reaction,
    )


async def dislike_post(email: str, post_id: int, db: AsyncSession) -> dict:
    logger.info(f"User {email} disliked post {post_id}")
    user = await require_user_by_email(email, db, logger)

    post = await db.execute(select(Post).filter_by(id=post_id))
    post = post.scalar_one_or_none()

    if post is None:
        logger.error(f"Post {post_id} was not found")
        raise HTTPException(status_code=400, detail="Post was not found")

    reaction = await db.execute(
        select(PostReaction).filter_by(
            post_id=post_id, user_id=user.id, reaction_type="like"
        )
    )

    reaction = reaction.scalar_one_or_none()

    if reaction is None:
        logger.info(f"User {email} has not liked post {post_id}")
        return {"message": "Not liked post", "status_code": 400}

    if post.post_likes > 0:
        post.post_likes -= 1
    else:
        logger.error(f"Trying to decrease less than zero post {post_id}")

    return await execute_db_operation(
        db,
        lambda: (
            db.delete(reaction),
            {"message": "Post liked successfully", "status_code": 200},
        )[-1],
        f"User {email} liked post {post_id}",
        f"Error while adding like to post {post_id} from {user}",
        logger,
        refresh_object=reaction,
    )
