from pydantic import BaseModel, ConfigDict
from datetime import datetime

class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class PostData(Base):
    id: int
    author_id: int
    created_at: datetime
    post_text: str
    post_likes: int
    post_image: str | None

class PostCreate(Base):
    post_text: str
    post_image: str | None