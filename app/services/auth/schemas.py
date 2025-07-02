from pydantic import BaseModel, field_validator, model_validator
from typing_extensions import Self


class UserAuthResponse(BaseModel):
    access_token: str
    refresh_token: str


class UserAuthLogin(BaseModel):
    email: str
    password: str


class UserUpdateRefresh(BaseModel):
    refresh_token: str


class UserAuthRegister(BaseModel):
    name: str
    username: str
    email: str
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
            raise ValueError("Password length should be more than 8")
        return v

    @field_validator("age")
    @classmethod
    def check_age(cls, v: int) -> int:
        if v < 14 or v > 100:
            raise ValueError("Age must be between 14 and 100")
        return v
