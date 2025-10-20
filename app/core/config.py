from pathlib import Path
from typing import Final
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from functools import lru_cache


class Settings(BaseSettings):
    JWT_SECRET_KEY: SecretStr = Field(..., description="JWT secret key")
    JWT_ALGORITHM: str = Field(..., description="JWT algorithm")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(30, gt=0)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(7, gt=0)
    postgres_db: str = Field(..., env='POSTGRES_DB')
    postgres_user: str = Field(..., env='POSTGRES_USER')
    postgres_password: SecretStr = Field(..., env='POSTGRES_PASSWORD')
    DB_URI: SecretStr = Field(default_factory=lambda s: SecretStr(f"postgresql+asyncpg://{s.postgres_user}:{s.postgres_password.get_secret_value()}@db:5432/{s.postgres_db}"))
    REDIS_URL: str = Field(..., description="Redis url")
    ACCESS_TOKEN_TTL: Final[int] = 15 * 60
    REFRESH_TOKEN_TTL: Final[int] = 7 * 24 * 60 * 60
    GCS_CREDENTIALS_PATH: str = Field(
        ..., description="Path to Google Cloud service account JSON file"
    )
    GCS_BUCKET_NAME: str = Field(
        ..., description="Bucket with profile pictures of users"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra='ignore',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.GCS_CREDENTIALS_PATH = str(
            Path(__file__).parent / self.GCS_CREDENTIALS_PATH
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
