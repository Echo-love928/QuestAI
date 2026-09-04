from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AI闯关学习 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:10086"]
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = Field(default="", repr=False)
    mysql_database: str = "AI-learn"
    wechat_app_id: str = ""
    wechat_app_secret: str = Field(default="", repr=False)
    jwt_secret: str = Field(default="", repr=False)
    jwt_expires_hours: int = 168
    upload_base_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
