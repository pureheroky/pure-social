from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import (
    Integer,
    String,
    Text,
    TIMESTAMP,
    ForeignKey,
)
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .post_reaction import PostReaction


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    post_text: Mapped[str] = mapped_column(Text)
    post_likes: Mapped[int] = mapped_column(Integer)
    post_dislikes: Mapped[int] = mapped_column(Integer)
    post_image: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    reactions: Mapped[List[PostReaction]] = relationship(
        "PostReaction", back_populates="post", cascade="all, delete-orphan"
    )
