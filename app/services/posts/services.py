from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models.post import Post
from .schemas import PostCreate, PostData
from utils.logger import setup_log
from utils.db_utils import get_user_by_email

logger = setup_log("posts", __name__)


async def get_posts(email: str, db: AsyncSession) -> List[PostData]:
    logger.info(f"Trying to get posts of user: {email}")
    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    result = await db.execute(select(Post).filter_by(author_id=user.id))
    posts = result.scalars().all()

    if not posts:
        logger.error(f"User {email} doesn't have any post")

    return [PostData.model_validate(post) for post in posts]

async def create_post(email: str, data: PostCreate, db: AsyncSession) -> PostData:
    logger.info(f"User {email} creating post")

    user = await get_user_by_email(email, db)
    if user is None:
        logger.error(f"User with email {email} was not found")
        raise HTTPException(status_code=400, detail="User was not found")

    new_post = Post(
        author_id=user.id,
        post_text=data.post_text,
        post_image=data.post_image,
        post_likes=0
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

async def delete_post(user_id: int, post_id: int, db: AsyncSession) -> dict:
    return {}
