from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional

from services.users.schemas import UserData


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class LikePostRequest(Base):
    post_id: int

class DislikePostRequest(Base):
    post_id: int

class AddCommentRequest(Base):
    post_id: int
    comment_text: str

class LikeCommentRequest(Base):
    comment_id: int

class DislikeCommentRequest(Base):
    comment_id: int

class DeleteCommentRequest(Base):
    comment_id: int

class EditPostRequest(Base):
    post_text: Optional[str] = None
    post_id: int
    remove_image: bool = False    


class PostCommentData(Base):
    id: int
    post_id: int
    user_id: int
    comment_text: str
    comment_likes: int
    comment_dislikes: int
    created_at: datetime
    updated_at: datetime
    user: UserData
    user_reaction: Optional[str] = None 


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
    user_reaction: Optional[str] = None 


class PostReactionData(Base):
    id: int
    post_id: int
    user_id: int
    reaction_type: str
    created_at: datetime
    updated_at: datetime = None