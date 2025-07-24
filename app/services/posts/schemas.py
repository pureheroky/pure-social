from pydantic import BaseModel, ConfigDict
from datetime import datetime
from db.models import Post
from db.models import User
from typing import Optional


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class PostData(Base):
    id: int
    author_id: int
    created_at: datetime
    post_text: str
    post_likes: int
    post_image: str | None


class PostReactionData(Base):
    id: int
    post_id: int
    user_id: int
    reaction_type: str
    created_at: datetime
    post: Optional[Post] = None
    user: Optional[User] = None
