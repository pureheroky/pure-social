from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class PostCommentData(Base):
    id: int
    post_id: int
    user_id: int
    comment_text: str
    comment_likes: int
    comment_dislikes: int
    created_at: datetime
    updated_at: datetime


class PostData(Base):
    id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    post_text: str
    post_likes: int
    post_dislikes: int
    post_image: str | None
    comments: List[PostCommentData] = []


class PostReactionData(Base):
    id: int
    post_id: int
    user_id: int
    reaction_type: str
    created_at: datetime
    updated_at: datetime = None
