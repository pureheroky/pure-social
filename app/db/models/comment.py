from __future__ import annotations
from typing import TYPE_CHECKING, List
from sqlalchemy import (
    Integer,
    String,
    TIMESTAMP,
    ForeignKey,
)
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .post import Post
    from .comment_reaction import CommentReaction


class Comment(Base):
    __tablename__ = "post_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("post.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    comment_text: Mapped[str] = mapped_column(String(500), nullable=False)
    comment_likes: Mapped[int] = mapped_column(Integer, default=0)
    comment_dislikes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reactions: Mapped[List[CommentReaction]] = relationship(
        "CommentReaction", back_populates="comment", cascade="all, delete-orphan"
    )
    post: Mapped[Post] = relationship("Post", back_populates="comments")
    user: Mapped[User] = relationship("User", back_populates="comments")
