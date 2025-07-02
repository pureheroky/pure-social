from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .schemas import UserData
from db.models.user import User
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

    try:
        img = Image.open(io.BytesIO(await file.read()))
        img.verify()
        file.file.seek(0)
        avatar_url = gcs_client.upload_file(file.file, file_ext, user_id)
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
