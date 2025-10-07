from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class ChatMessageCreate(Base):
    content: str
    type: MessageType = MessageType.TEXT
    reply_to_id: Optional[int] = None


class ChatMessageResponse(Base):
    id: int
    chat_id: int
    sender_id: int
    content: str
    type: MessageType
    reply_to_id: Optional[int]
    status: MessageStatus
    created_at: datetime
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]


class ChatResponse(Base):
    id: int
    user1_id: int
    user2_id: int
    created_at: datetime
    last_message: Optional[ChatMessageResponse]
    unread_count: int = 0


class ChatListResponse(Base):
    chats: List[ChatResponse]


class UploadMediaResponse(Base):
    url: str
    type: MessageType
