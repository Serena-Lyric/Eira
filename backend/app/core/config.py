import os
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]


class DBSettings(BaseModel):
    dsn: str = "postgresql+asyncpg://eira:eira@localhost:5432/eira"


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"


class OssSettings(BaseModel):
    endpoint: str = "http://localhost:9000"
    key: str = "eira"
    secret: str = "eira-secret"
    region: str = "us-east-1"


class JwtSettings(BaseModel):
    secret: str = "dev-only-change-me"
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 7 * 24 * 3600
    algorithm: str = "HS256"


class LlmSettings(BaseModel):
    provider: Literal["deepseek", "openai", "tongyi", "volc", "mock"] = "deepseek"
    # 从环境变量 EIRA_LLM__API_KEY 注入，默认空串（切勿在源码硬编码密钥）
    api_key: str = ""
    api_base: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = 2048
    temperature: float = 0.7
    max_retries: int = 3
    request_timeout: int = 60


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EIRA_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )
    app: AppSettings = AppSettings()
    db: DBSettings = DBSettings()
    redis: RedisSettings = RedisSettings()
    oss: OssSettings = OssSettings()
    jwt: JwtSettings = JwtSettings()
    llm: LlmSettings = LlmSettings()


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if v := os.environ.get("EIRA_DB_DSN"):
        s.db.dsn = v
    if v := os.environ.get("EIRA_REDIS_URL"):
        s.redis.url = v
    if v := os.environ.get("EIRA_OSS_ENDPOINT"):
        s.oss.endpoint = v
    return s
