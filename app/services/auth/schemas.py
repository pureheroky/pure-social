from pydantic import BaseModel, ConfigDict, field_validator, model_validator, EmailStr
from typing_extensions import Self
from services.users.schemas import UserData



class Base(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class UserAuthResponse(Base):
    access_token: str
    refresh_token: str
    user: UserData


class UserAuthLogin(Base):
    email: EmailStr
    password: str


class UserAuthRegister(Base):
    name: str
    username: str
    email: EmailStr
    password: str
    repeat_password: str
    age: int

    @model_validator(mode="after")
    def check_password_match(self) -> Self:
        if self.password != self.repeat_password:
            raise ValueError("Passwords do not match")
        return self

    @field_validator("password")
    @classmethod
    def check_password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password length should be at least 8 characters")
        return v

    @field_validator("age")
    @classmethod
    def check_age(cls, v: int) -> int:
        if v < 14 or v > 100:
            raise ValueError("Age must be between 14 and 100")
        return v