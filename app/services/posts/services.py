from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from db.models.post import Post
from db.models.comment import Comment
from db.models.comment_reaction import CommentReaction
from db.models.post_reaction import PostReaction, ReactionType
from utils.db_utils import require_comment_author
from .schemas import PostData, PostCommentData
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
ALLOWED_EXTENSIONS = {".jpg", ".png", ".webp", ".jpeg"}


async def get_posts(
    email: str, db: AsyncSession, limit: int = 50, offset: int = 0
) -> List[PostData]:
    """Retrieve all posts for a user with pagination."""
    logger.info(f"Trying to get posts for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    query = (
        select(Post)
        .filter_by(author_id=user.id)
        .options(selectinload(Post.comments))
        .limit(limit)
        .offset(offset)
        .order_by(Post.created_at.desc())
    )
    result = await db.execute(query)
    posts = result.scalars().all()

    if not posts:
        logger.info(f"User {user.id} has no posts")
        return []

    return [PostData.model_validate(post) for post in posts]


async def create_post(
    email: str,
    post_text: str,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    """Create a new post with optional image."""
    logger.info(f"Creating post for user email: {email[:5]}...")
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
        post_dislikes=0,
    )

    async def operation() -> PostData:
        db.add(new_post)
        await db.flush()
        await db.refresh(new_post, attribute_names=["comments"])
        return PostData.model_validate(new_post)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully created new post for user {user.id}",
        f"Error creating post for user {user.id}",
        logger,
        refresh_object=new_post,
        use_flush=True,
    )


async def delete_post(email: str, post_id: int, db: AsyncSession) -> dict:
    """Delete a post if the user is the author."""
    logger.info(f"Deleting post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    post = await require_post_author(post_id, user.id, db, logger)

    if post.post_image:
        parsed_url = urlparse(post.post_image)
        old_blob_name = parsed_url.path.lstrip("/")
        if "?" in old_blob_name:
            old_blob_name = old_blob_name.split("?")[0]
        try:
            gcs_client.delete_file(old_blob_name)
        except Exception as e:
            logger.error(f"Failed to delete image for post {post_id}: {e}")

    async def operation() -> dict:
        await db.execute(delete(Post).where(Post.id == post_id))
        await db.flush()
        return {"detail": "Post deleted successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully deleted post {post_id} for user {user.id}",
        f"Error deleting post {post_id} for user {user.id}",
        logger,
    )


async def edit_post(
    email: str,
    post_text: Optional[str],
    post_id: int,
    remove_image: bool,
    db: AsyncSession,
    post_image: Optional[UploadFile] = None,
) -> PostData:
    """Edit post text and/or image."""
    logger.info(f"Editing post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    post = await require_post_author(post_id, user.id, db, logger)

    if post_text is not None:
        post.post_text = post_text

    if remove_image:
        if post.post_image:
            parsed_url = urlparse(post.post_image)
            old_blob_name = parsed_url.path.lstrip("/")
            if "?" in old_blob_name:
                old_blob_name = old_blob_name.split("?")[0]
            try:
                gcs_client.delete_file(old_blob_name)
            except Exception as e:
                logger.error(f"Failed to delete image for post {post_id}: {e}")
            post.post_image = None
    elif post_image:
        if post.post_image:
            parsed_url = urlparse(post.post_image)
            old_blob_name = parsed_url.path.lstrip("/")
            if "?" in old_blob_name:
                old_blob_name = old_blob_name.split("?")[0]
            try:
                gcs_client.delete_file(old_blob_name)
            except Exception as e:
                logger.error(f"Failed to delete old image for post {post_id}: {e}")
        post_image_url = await validate_and_upload_image(
            db, post_image, ALLOWED_EXTENSIONS, gcs_client, logger, user.id, "posts"
        )
        post.post_image = post_image_url

    post.updated_at = datetime.now(timezone.utc)

    async def operation() -> PostData:
        await db.flush()
        await db.refresh(post, attribute_names=["comments"])
        return PostData.model_validate(post)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully edited post {post_id}",
        f"Error editing post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def get_reacted_posts(email: str, db: AsyncSession) -> List[PostData]:
    """Retrieve posts that the user has reacted to, deduplicated."""
    logger.info(f"Retrieving reacted posts for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    query = (
        select(Post)
        .distinct()
        .join(PostReaction, Post.id == PostReaction.post_id)
        .filter(PostReaction.user_id == user.id)
        .options(selectinload(Post.comments))
        .order_by(Post.created_at.desc())
    )
    result = await db.execute(query)
    posts = result.scalars().all()

    if not posts:
        logger.info(f"No reacted posts found for user {user.id}")
        return []

    return [PostData.model_validate(post) for post in posts]


async def like_post(email: str, post_id: int, db: AsyncSession) -> dict:
    """Like a post, switching reaction if present, and update counters."""
    logger.info(f"Liking post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_result = await db.execute(
        select(PostReaction).filter_by(post_id=post_id, user_id=user.id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.reaction_type == ReactionType.LIKE:
        raise HTTPException(status_code=400, detail="Already liked")

    async def operation() -> dict:
        if existing:
            if existing.reaction_type == ReactionType.DISLIKE:
                existing.reaction_type = ReactionType.LIKE
                existing.updated_at = datetime.now(timezone.utc)
                await db.execute(
                    update(PostReaction)
                    .where(PostReaction.id == existing.id)
                    .values(
                        reaction_type=ReactionType.LIKE, updated_at=existing.updated_at
                    )
                )
                post.post_dislikes -= 1
                post.post_likes += 1
        else:
            new_reaction = PostReaction(
                post_id=post_id,
                user_id=user.id,
                reaction_type=ReactionType.LIKE,
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_reaction)
            post.post_likes += 1

        await db.flush()
        await db.refresh(post)

        post.post_likes = max(0, post.post_likes)
        post.post_dislikes = max(0, post.post_dislikes)

        return {"detail": "Post liked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully liked post {post_id} for user {user.id}",
        f"Error liking post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def dislike_post(email: str, post_id: int, db: AsyncSession) -> dict:
    """Dislike a post, switching reaction if present, and update counters."""
    logger.info(f"Disliking post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing_result = await db.execute(
        select(PostReaction).filter_by(post_id=post_id, user_id=user.id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.reaction_type == ReactionType.DISLIKE:
        raise HTTPException(status_code=400, detail="Already disliked")

    async def operation() -> dict:
        if existing:
            if existing.reaction_type == ReactionType.LIKE:
                existing.reaction_type = ReactionType.DISLIKE
                existing.updated_at = datetime.now(timezone.utc)
                await db.execute(
                    update(PostReaction)
                    .where(PostReaction.id == existing.id)
                    .values(
                        reaction_type=ReactionType.DISLIKE,
                        updated_at=existing.updated_at,
                    )
                )
                post.post_likes -= 1
                post.post_dislikes += 1
        else:
            new_reaction = PostReaction(
                post_id=post_id,
                user_id=user.id,
                reaction_type=ReactionType.DISLIKE,
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_reaction)
            post.post_dislikes += 1

        await db.flush()
        await db.refresh(post)

        post.post_likes = max(0, post.post_likes)
        post.post_dislikes = max(0, post.post_dislikes)

        return {"detail": "Post disliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully disliked post {post_id} for user {user.id}",
        f"Error disliking post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def unlike_post(email: str, post_id: int, db: AsyncSession) -> dict:
    """Remove like from a post and update counters."""
    logger.info(f"Unliking post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    reaction_result = await db.execute(
        select(PostReaction).filter_by(
            post_id=post_id, user_id=user.id, reaction_type=ReactionType.LIKE
        )
    )
    reaction = reaction_result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=400, detail="Post not liked")

    async def operation() -> dict:
        await db.delete(reaction)
        post.post_likes -= 1
        await db.flush()
        await db.refresh(post)

        post.post_likes = max(0, post.post_likes)
        post.post_dislikes = max(0, post.post_dislikes)

        return {"detail": "Post unliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully unliked post {post_id} for user {user.id}",
        f"Error unliking post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def undislike_post(email: str, post_id: int, db: AsyncSession) -> dict:
    """Remove dislike from a post and update counters."""
    logger.info(f"Undisliking post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    reaction_result = await db.execute(
        select(PostReaction).filter_by(
            post_id=post_id, user_id=user.id, reaction_type=ReactionType.DISLIKE
        )
    )
    reaction = reaction_result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=400, detail="Post not disliked")

    async def operation() -> dict:
        await db.delete(reaction)
        post.post_dislikes -= 1
        await db.flush()
        await db.refresh(post)

        post.post_likes = max(0, post.post_likes)
        post.post_dislikes = max(0, post.post_dislikes)

        return {"detail": "Post undisliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully undisliked post {post_id} for user {user.id}",
        f"Error undisliking post {post_id}",
        logger,
        refresh_object=post,
        use_flush=True,
    )


async def get_comments(post_id: int, db: AsyncSession) -> List[PostCommentData]:
    """Retrieve all comments for a post with reactions."""
    logger.info(f"Retrieving comments for post {post_id}...")
    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    query = (
        select(Comment)
        .filter_by(post_id=post_id)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.reactions),
        )
        .order_by(Comment.created_at.asc())
    )
    result = await db.execute(query)
    comments = result.scalars().all()

    return [PostCommentData.model_validate(comment) for comment in comments]


async def add_comment(
    post_id: int, comment_text: str, email: str, db: AsyncSession
) -> PostCommentData:
    """Add a new comment to a post."""
    logger.info(f"Adding comment to post {post_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    post_result = await db.execute(select(Post).filter_by(id=post_id))
    post = post_result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_comment = Comment(
        post_id=post_id,
        user_id=user.id,
        comment_text=comment_text,
        comment_likes=0,
        comment_dislikes=0,
    )

    async def operation() -> PostCommentData:
        db.add(new_comment)
        await db.flush()
        await db.refresh(new_comment, attribute_names=["user"])
        return PostCommentData.model_validate(new_comment)

    return await execute_db_operation(
        db,
        operation,
        f"Successfully added comment to post {post_id} for user {user.id}",
        f"Error adding comment to post {post_id}",
        logger,
        refresh_object=new_comment,
        use_flush=True,
    )


async def delete_comment(email: str, comment_id: int, db: AsyncSession) -> dict:
    """Delete a comment if the user is the author."""
    logger.info(f"Deleting comment {comment_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)
    comment = await require_comment_author(comment_id, user.id, db, logger)

    async def operation() -> dict:
        await db.execute(delete(Comment).where(Comment.id == comment_id))
        await db.flush()
        return {"detail": "Comment deleted successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully deleted comment {comment_id} for user {user.id}",
        f"Error deleting comment {comment_id} for user {user.id}",
        logger,
    )


async def like_comment(email: str, comment_id: int, db: AsyncSession) -> dict:
    """Like a comment, switching reaction if present, and update counters."""
    logger.info(f"Liking comment {comment_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    comment_result = await db.execute(select(Comment).filter_by(id=comment_id))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing_result = await db.execute(
        select(CommentReaction).filter_by(comment_id=comment_id, user_id=user.id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.reaction_type == ReactionType.LIKE:
        raise HTTPException(status_code=400, detail="Already liked")

    async def operation() -> dict:
        if existing:
            if existing.reaction_type == ReactionType.DISLIKE:
                existing.reaction_type = ReactionType.LIKE
                existing.updated_at = datetime.now(timezone.utc)
                await db.execute(
                    update(CommentReaction)
                    .where(CommentReaction.id == existing.id)
                    .values(
                        reaction_type=ReactionType.LIKE, updated_at=existing.updated_at
                    )
                )
                comment.comment_dislikes -= 1
                comment.comment_likes += 1
        else:
            new_reaction = CommentReaction(
                comment_id=comment_id,
                user_id=user.id,
                reaction_type=ReactionType.LIKE,
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_reaction)
            comment.comment_likes += 1

        await db.flush()
        await db.refresh(comment)

        comment.comment_likes = max(0, comment.comment_likes)
        comment.comment_dislikes = max(0, comment.comment_dislikes)

        return {"detail": "Comment liked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully liked comment {comment_id} for user {user.id}",
        f"Error liking comment {comment_id}",
        logger,
        refresh_object=comment,
        use_flush=True,
    )


async def dislike_comment(email: str, comment_id: int, db: AsyncSession) -> dict:
    """Dislike a comment, switching reaction if present, and update counters."""
    logger.info(f"Disliking comment {comment_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    comment_result = await db.execute(select(Comment).filter_by(id=comment_id))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing_result = await db.execute(
        select(CommentReaction).filter_by(comment_id=comment_id, user_id=user.id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing and existing.reaction_type == ReactionType.DISLIKE:
        raise HTTPException(status_code=400, detail="Already disliked")

    async def operation() -> dict:
        if existing:
            if existing.reaction_type == ReactionType.LIKE:
                existing.reaction_type = ReactionType.DISLIKE
                existing.updated_at = datetime.now(timezone.utc)
                await db.execute(
                    update(CommentReaction)
                    .where(CommentReaction.id == existing.id)
                    .values(
                        reaction_type=ReactionType.DISLIKE,
                        updated_at=existing.updated_at,
                    )
                )
                comment.comment_likes -= 1
                comment.comment_dislikes += 1
        else:
            new_reaction = CommentReaction(
                comment_id=comment_id,
                user_id=user.id,
                reaction_type=ReactionType.DISLIKE,
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_reaction)
            comment.comment_dislikes += 1

        await db.flush()
        await db.refresh(comment)

        comment.comment_likes = max(0, comment.comment_likes)
        comment.comment_dislikes = max(0, comment.comment_dislikes)

        return {"detail": "Comment disliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully disliked comment {comment_id} for user {user.id}",
        f"Error disliking comment {comment_id}",
        logger,
        refresh_object=comment,
        use_flush=True,
    )


async def unlike_comment(email: str, comment_id: int, db: AsyncSession) -> dict:
    """Remove like from a comment and update counters."""
    logger.info(f"Unliking comment {comment_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    comment_result = await db.execute(select(Comment).filter_by(id=comment_id))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reaction_result = await db.execute(
        select(CommentReaction).filter_by(
            comment_id=comment_id, user_id=user.id, reaction_type=ReactionType.LIKE
        )
    )
    reaction = reaction_result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=400, detail="Comment not liked")

    async def operation() -> dict:
        await db.delete(reaction)
        comment.comment_likes -= 1
        await db.flush()
        await db.refresh(comment)

        comment.comment_likes = max(0, comment.comment_likes)
        comment.comment_dislikes = max(0, comment.comment_dislikes)

        return {"detail": "Comment unliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully unliked comment {comment_id} for user {user.id}",
        f"Error unliking comment {comment_id}",
        logger,
        refresh_object=comment,
        use_flush=True,
    )


async def undislike_comment(email: str, comment_id: int, db: AsyncSession) -> dict:
    """Remove dislike from a comment and update counters."""
    logger.info(f"Undisliking comment {comment_id} for user email: {email[:5]}...")
    user = await require_user_by_email(email, db, logger)

    comment_result = await db.execute(select(Comment).filter_by(id=comment_id))
    comment = comment_result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reaction_result = await db.execute(
        select(CommentReaction).filter_by(
            comment_id=comment_id, user_id=user.id, reaction_type=ReactionType.DISLIKE
        )
    )
    reaction = reaction_result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=400, detail="Comment not disliked")

    async def operation() -> dict:
        await db.delete(reaction)
        comment.comment_dislikes -= 1
        await db.flush()
        await db.refresh(comment)

        comment.comment_likes = max(0, comment.comment_likes)
        comment.comment_dislikes = max(0, comment.comment_dislikes)

        return {"detail": "Comment undisliked successfully"}

    return await execute_db_operation(
        db,
        operation,
        f"Successfully undisliked comment {comment_id} for user {user.id}",
        f"Error undisliking comment {comment_id}",
        logger,
        refresh_object=comment,
        use_flush=True,
    )
