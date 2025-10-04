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


# @event.listens_for(PostReaction, "after_insert")
# def after_insert_post_reaction(mapper, connection, target):
#     from .post import Post

#     session = object_session(target)
#     if not session:
#         return

#     post = session.get(Post, target.post_id)

#     if target.reaction_type == ReactionType.LIKE:
#         post.post_likes = (post.post_likes or 0) + 1
#     elif target.reaction_type == ReactionType.DISLIKE:
#         post.post_dislikes = (post.post_dislikes or 0) + 1


# @event.listens_for(PostReaction, "after_delete")
# def after_delete_post_reaction(mapper, connection, target):
#     from .post import Post

#     session = object_session(target)
#     if not session:
#         return

#     post = session.get(Post, target.post_id)

#     if target.reaction_type == ReactionType.LIKE:
#         post.post_likes = max((post.post_likes or 0) - 1, 0)
#     elif target.reaction_type == ReactionType.DISLIKE:
#         post.post_dislikes = max((post.post_dislikes or 0) - 1, 0)
