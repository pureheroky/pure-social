from datetime import datetime
from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserData(Base):
    id: int
    name: str
    created_at: datetime
    custom_url: str
    age: int
    username: str
    profile_pic: str | None


class FriendshipData(Base):
    user_id: int
    friend_id: int
    status: str
    requested_at: datetime
    accepted_at: datetime | None


class UserDataDetailed(UserData):
    email: str
    password_hash: str
    friendshipid: int
