from __future__ import annotations
from sqlalchemy import Integer, TIMESTAMP, ForeignKey, Enum, UniqueConstraint
from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session
from sqlalchemy import event
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


# @event.listens_for(CommentReaction, "after_insert")
# def after_insert_comment_reaction(mapper, connection, target):
#     from .comment import Comment

#     session = object_session(target)
#     if not session:
#         return

#     comment = session.get(Comment, target.comment_id)

#     if target.reaction_type == ReactionType.LIKE:
#         comment.comment_likes = (comment.comment_likes or 0) + 1
#     elif target.reaction_type == ReactionType.DISLIKE:
#         comment.comment_dislikes = (comment.comment_dislikes or 0) + 1


# @event.listens_for(CommentReaction, "after_delete")
# def after_delete_comment_reaction(mapper, connection, target):
#     from .comment import Comment

#     session = object_session(target)
#     if not session:
#         return

#     comment = session.get(Comment, target.comment_id)

#     if target.reaction_type == ReactionType.LIKE:
#         comment.comment_likes = max(0, (comment.comment_likes or 0) - 1)
#     elif target.reaction_type == ReactionType.DISLIKE:
#         comment.comment_dislikes = max(0, (comment.comment_dislikes or 0) - 1)
