from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AI闯关学习 API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    tavily_api_key: str = Field(default="", repr=False)
    web_research_enabled: bool = False
    research_total_timeout_seconds: int = Field(default=45, ge=5, le=120)
    research_tool_timeout_seconds: int = Field(default=20, ge=1, le=60)
    research_max_tool_calls: int = Field(default=4, ge=1, le=8)
    research_max_search_calls: int = Field(default=2, ge=1, le=4)
    research_max_search_results: int = Field(default=8, ge=3, le=20)
    research_max_extract_urls: int = Field(default=3, ge=1, le=10)
    research_max_evidence_chars: int = Field(default=24_000, ge=4_000, le=100_000)
    research_full_material_min_chars: int = Field(default=300, ge=100, le=5_000)
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

    @model_validator(mode="after")
    def validate_research_settings(self) -> "Settings":
        if self.web_research_enabled and not self.tavily_api_key:
            raise ValueError("启用联网研究时缺少 TAVILY_API_KEY")
        if self.research_tool_timeout_seconds >= self.research_total_timeout_seconds:
            raise ValueError("研究工具超时必须小于研究总超时")
        if self.research_max_search_calls > self.research_max_tool_calls:
            raise ValueError("搜索调用上限不能超过工具调用总上限")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
