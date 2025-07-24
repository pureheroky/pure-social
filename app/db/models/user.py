from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import (
    Integer,
    String,
    Text,
    TIMESTAMP,
)
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .base import Base

if TYPE_CHECKING:
    from .friendship import Friendship
    from .post_reaction import PostReaction
else:
    from .friendship import Friendship
    from .post_reaction import PostReaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
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
    friendshipid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    custom_url: Mapped[str] = mapped_column(String(16))
    age: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    profile_pic: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    friends: Mapped[List[Friendship]] = relationship(
        "Friendship",
        foreign_keys=[Friendship.user_id],
        back_populates="user",
        cascade="all, delete-orphan",
    )

    friends_of: Mapped[List[Friendship]] = relationship(
        "Friendship",
        foreign_keys=[Friendship.friend_id],
        back_populates="friend",
        cascade="all, delete-orphan",
    )

    reactions: Mapped[List[PostReaction]] = relationship(
        "PostReaction", back_populates="user", cascade="all, delete-orphan"
    )
