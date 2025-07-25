from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import (
    Integer,
    String,
    TIMESTAMP,
    ForeignKey,
)
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .base import Base


if TYPE_CHECKING:
    from .user import User


class Friendship(Base):
    __tablename__ = "friendship"
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    friend_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    requested_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="friends"
    )
    friend: Mapped["User"] = relationship(
        "User", foreign_keys=[friend_id], back_populates="friends_of"
    )
