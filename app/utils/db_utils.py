from db.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).filter_by(id=user_id))
    return result.scalar_one_or_none()

async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    user_req = await db.execute(select(User).filter_by(email=email))
    return user_req.scalar_one_or_none()