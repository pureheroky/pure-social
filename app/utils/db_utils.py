from db.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def check_user_exists(user_id: int, db: AsyncSession) -> bool:
    result = await db.execute(select(User).filter_by(id=user_id))
    return result.scalar_one_or_none() is not None
