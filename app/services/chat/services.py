import json
from fastapi import HTTPException, WebSocket, UploadFile
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import List, Optional, Dict
from enum import Enum
from utils.db_utils import execute_db_operation
from utils.logger import setup_log
from utils.gcs_manager import GCSManager
from core.config import get_settings
from db.models.chat import Chat
from db.models.message import Message, MessageStatus
from db.models.friendship import Friendship, FriendshipStatus
from .schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatResponse,
    ChatListResponse,
    UploadMediaResponse,
    MessageType,
)
from utils.websocket_manager import ConnectionManager

settings = get_settings()
logger = setup_log("chat", __name__)
gcs_client = GCSManager(settings.GCS_BUCKET_NAME)
manager = ConnectionManager()
ALLOWED_IMAGE_EXT = {".jpg", ".png", ".webp", ".jpeg"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov"}


class MediaFolder(Enum):
    IMAGES = "chat_images"
    VIDEOS = "chat_videos"


friendship_cache: Dict[tuple[int, int], FriendshipStatus] = {}


async def get_friendship_status(
    user1_id: int, user2_id: int, db: AsyncSession
) -> FriendshipStatus:
    key = tuple(sorted([user1_id, user2_id]))
    if key in friendship_cache:
        return friendship_cache[key]
    result = await db.execute(
        select(Friendship).filter(
            or_(
                and_(Friendship.user_id == user1_id, Friendship.friend_id == user2_id),
                and_(Friendship.user_id == user2_id, Friendship.friend_id == user1_id),
            )
        )
    )
    friendship = result.scalar_one_or_none()
    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(status_code=403, detail="Users are not friends")
    friendship_cache[key] = friendship.status
    return friendship.status


async def get_or_create_chat(user1_id: int, user2_id: int, db: AsyncSession) -> Chat:
    await get_friendship_status(user1_id, user2_id, db)

    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id

    result = await db.execute(
        select(Chat).filter_by(user1_id=user1_id, user2_id=user2_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        now = datetime.now(timezone.utc)
        chat = Chat(user1_id=user1_id, user2_id=user2_id, created_at=now)
        db.add(chat)
        await db.flush()
    return chat


async def send_message(
    data: ChatMessageCreate,
    sender_id: int,
    receiver_id: int,
    db: AsyncSession,
    websocket: Optional[WebSocket] = None,
) -> ChatMessageResponse:
    chat = await get_or_create_chat(sender_id, receiver_id, db)

    async def operation():
        message = Message(
            chat_id=chat.id,
            sender_id=sender_id,
            content=data.content,
            type=data.type.value,
            reply_to_id=data.reply_to_id,
            status=MessageStatus.SENT,
            created_at=datetime.now(timezone.utc),
        )
        db.add(message)
        await db.flush()
        await db.refresh(message)
        return ChatMessageResponse.model_validate(message)

    try:
        msg = await execute_db_operation(
            db,
            operation,
            "Message sent",
            "Error sending message",
            logger,
            use_flush=True,
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    broadcast_data = {"type": "message", "data": msg.model_dump()}
    await manager.send_personal(broadcast_data, receiver_id)

    if websocket:
        await websocket.send_text(json.dumps(broadcast_data))

    if await manager.is_online(receiver_id):

        async def update_status():
            result = await db.execute(select(Message).filter_by(id=msg.id))
            message = result.scalar_one_or_none()
            if message:
                message.status = MessageStatus.DELIVERED
                message.delivered_at = datetime.now(timezone.utc)
                await db.flush()
                await db.refresh(message)

        try:
            await execute_db_operation(
                db,
                update_status,
                "Status updated to delivered",
                "Error updating status",
                logger,
            )
            status_update = {
                "type": "status_update",
                "message_id": msg.id,
                "status": "delivered",
            }
            await manager.send_personal(status_update, sender_id)
        except Exception as e:
            logger.error(f"Failed to update delivered status: {e}")

    return msg


async def upload_media(
    file: UploadFile,
    chat_id: int,
    sender_id: int,
    media_type: MessageType,
    db: AsyncSession,
) -> UploadMediaResponse:
    try:
        if file.size > 10 * 1024 * 1024:
            raise HTTPException(400, detail="File too large (max 10MB)")
        chat = await require_chat_by_id(chat_id, sender_id, db)
        receiver_id = chat.user2_id if chat.user1_id == sender_id else chat.user1_id

        if media_type == MessageType.IMAGE:
            allowed = ALLOWED_IMAGE_EXT
            folder = MediaFolder.IMAGES.value
        elif media_type == MessageType.VIDEO:
            allowed = ALLOWED_VIDEO_EXT
            folder = MediaFolder.VIDEOS.value
        else:
            raise HTTPException(400, detail="Invalid media type")

        file_ext = f".{file.filename.split('.')[-1].lower()}" if file.filename else ""
        if file_ext not in allowed:
            raise HTTPException(400, detail="Unsupported file format")

        content = await file.read()
        blob_name = (
            f"{folder}/{sender_id}/{chat_id}/{datetime.now().timestamp()}{file_ext}"
        )
        gcs_client.upload_bytes(content, blob_name)
        url = gcs_client.get_signed_url(blob_name, expiration=3600 * 24 * 365)

        return UploadMediaResponse(url=url, type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


async def get_chat_list(user_id: int, db: AsyncSession) -> ChatListResponse:
    subq = (
        select(Chat.id)
        .filter(or_(Chat.user1_id == user_id, Chat.user2_id == user_id))
        .subquery()
    )

    result = await db.execute(
        select(Chat)
        .options(selectinload(Chat.messages))
        .filter(Chat.id.in_(subq))
        .order_by(Chat.created_at.desc())
    )
    chats = result.scalars().all()

    chat_list = []
    for chat in chats:
        other_user_id = chat.user2_id if chat.user1_id == user_id else chat.user1_id
        await get_friendship_status(user_id, other_user_id, db)

        last_result = await db.execute(
            select(Message)
            .filter_by(chat_id=chat.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = last_result.scalar_one_or_none()

        unread_result = await db.execute(
            select(func.count(Message.id)).filter(
                and_(
                    Message.chat_id == chat.id,
                    Message.sender_id != user_id,
                    Message.status != MessageStatus.READ,
                )
            )
        )
        unread_count = unread_result.scalar()

        chat_resp = ChatResponse.model_validate(chat)
        chat_resp.last_message = (
            ChatMessageResponse.model_validate(last_msg) if last_msg else None
        )
        chat_resp.unread_count = unread_count
        chat_list.append(chat_resp)

    return ChatListResponse(chats=chat_list)


async def get_messages(
    chat_id: int,
    user_id: int,
    db: AsyncSession,
    limit: int = 50,
    before_id: Optional[int] = None,
) -> List[ChatMessageResponse]:
    chat = await require_chat_by_id(chat_id, user_id, db)

    query = (
        select(Message)
        .filter_by(chat_id=chat_id)
        .options(selectinload(Message.reply_to))
    )
    if before_id:
        query = query.filter(Message.id < before_id)
    query = query.order_by(Message.created_at.desc()).limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()
    messages.reverse()
    return [ChatMessageResponse.model_validate(m) for m in messages]


async def mark_as_read(chat_id: int, user_id: int, db: AsyncSession):
    chat = await require_chat_by_id(chat_id, user_id, db)
    sender_id = chat.user1_id if chat.user2_id == user_id else chat.user2_id

    result = await db.execute(
        select(Message).filter(
            and_(
                Message.chat_id == chat_id,
                Message.sender_id == sender_id,
                Message.status != MessageStatus.READ,
            )
        )
    )
    messages = result.scalars().all()

    if not messages:
        return

    now = datetime.now(timezone.utc)
    for msg in messages:
        msg.status = MessageStatus.READ
        msg.read_at = now

    await db.flush()

    for msg in messages:
        try:
            status_update = {
                "type": "status_update",
                "message_id": msg.id,
                "status": "read",
            }
            await manager.send_personal(status_update, sender_id)
        except Exception as e:
            logger.error(f"Failed to send read status for msg {msg.id}: {e}")


async def require_chat_by_id(chat_id: int, user_id: int, db: AsyncSession) -> Chat:
    result = await db.execute(
        select(Chat).filter(
            or_(
                and_(Chat.user1_id == user_id, Chat.id == chat_id),
                and_(Chat.user2_id == user_id, Chat.id == chat_id),
            )
        )
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(404, detail="Chat not found")
    await get_friendship_status(chat.user1_id, chat.user2_id, db)
    return chat
