import json
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    File,
    UploadFile,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from core.security import get_current_user_id
from ..schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatListResponse,
    UploadMediaResponse,
    MessageType,
)
from ..services import (
    send_message,
    get_chat_list,
    get_messages,
    upload_media,
    mark_as_read,
    require_chat_by_id,
)
from utils.websocket_manager import ConnectionManager
from utils.logger import setup_log

logger = setup_log("chat", __name__)
manager = ConnectionManager()
router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status":"ok"}

@router.get("/list", response_model=ChatListResponse)
async def list_chats(
    user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    return await get_chat_list(user_id, db)


@router.post("/messages/{chat_id}", response_model=ChatMessageResponse)
async def send_text_message(
    chat_id: int,
    data: ChatMessageCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    receiver_id = await get_receiver_id(chat_id, user_id, db)
    return await send_message(data, user_id, receiver_id, db)


@router.post("/upload/{chat_id}/{media_type}", response_model=UploadMediaResponse)
async def upload_media_endpoint(
    chat_id: int,
    media_type: MessageType,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await upload_media(file, chat_id, user_id, media_type, db)


@router.get("/{chat_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_messages(chat_id, user_id, db, limit, before_id)


@router.post("/{chat_id}/read")
async def mark_read(
    chat_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await mark_as_read(chat_id, user_id, db)
    return {"status": "ok"}


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token"),
    db: AsyncSession = Depends(get_db),
):
    user_id = await manager.connect(websocket, token)
    if not user_id:
        logger.warning("Invalid connection attempt")
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            action = payload.get("action")
            if action == "send":
                msg_data = ChatMessageCreate(**payload["data"])
                chat_id = payload.get("chat_id")
                if chat_id:
                    receiver_id = await get_receiver_id(chat_id, user_id, db)
                else:
                    receiver_id = payload.get("receiver_id", 0)
                    if not receiver_id:
                        await websocket.send_text(
                            json.dumps({"error": "Missing receiver"})
                        )
                        continue
                await send_message(msg_data, user_id, receiver_id, db, websocket)

            elif action == "read":
                chat_id = payload.get("chat_id")
                if chat_id:
                    await mark_as_read(chat_id, user_id, db)
                else:
                    await websocket.send_text(json.dumps({"error": "Missing chat_id"}))

            else:
                await websocket.send_text(json.dumps({"error": "Unknown action"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error for user {user_id}: {e}")
    finally:
        await manager.disconnect(user_id)
        logger.info(f"User {user_id} disconnected")


async def get_receiver_id(chat_id: int, user_id: int, db: AsyncSession) -> int:
    chat = await require_chat_by_id(chat_id, user_id, db)
    return chat.user2_id if chat.user1_id == user_id else chat.user1_id
