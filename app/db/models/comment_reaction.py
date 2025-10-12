from __future__ import annotations
from sqlalchemy import Integer, TIMESTAMP, ForeignKey, Enum, UniqueConstraint
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .post_reaction import ReactionType

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .comment import Comment


class CommentReaction(Base):
    __tablename__ = "comment_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    comment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False
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

    comment: Mapped[Comment] = relationship("Comment", back_populates="reactions")
    user: Mapped[User] = relationship("User", back_populates="comment_reactions")

    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_comment_user_reaction"),
    )
