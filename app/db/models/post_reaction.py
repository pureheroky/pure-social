from __future__ import annotations
from enum import Enum as PyEnum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, TIMESTAMP, ForeignKey, Enum, UniqueConstraint
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session
from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .post import Post


class ReactionType(PyEnum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class PostReaction(Base):
    __tablename__ = "post_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("post.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reaction_type: Mapped[ReactionType] = mapped_column(
        Enum(ReactionType), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    post: Mapped[Post] = relationship("Post", back_populates="reactions")
    user: Mapped[User] = relationship("User", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_post_user_reaction"),
    )


