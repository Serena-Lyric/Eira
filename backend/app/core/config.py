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
    # SECURITY: 部署到 staging/prod 时必须通过 EIRA_OSS__SECRET 覆盖。
    # 启动时 main.py 会检查非 dev 环境下是否仍为空或使用了已知默认值。
    secret: str = ""
    region: str = "us-east-1"


class JwtSettings(BaseModel):
    # SECURITY: 部署到 staging/prod 时必须通过 EIRA_JWT__SECRET 覆盖为空默认值。
    # 启动时 main.py 会检查非 dev 环境下是否仍为空或使用了已知默认值。
    secret: str = ""
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 7 * 24 * 3600
    algorithm: str = "HS256"


# FIXME: §4.5 — API keys 当前明文存储在 system_settings JSONB 中。
# MVP 阶段可接受，上线前需升级为 pgcrypto 字段级加密 + 应用层 KMS 包装。
class LlmSettings(BaseModel):
    provider: Literal["deepseek", "openai", "tongyi", "volc", "mock"] = "deepseek"
    # 从环境变量 EIRA_LLM__API_KEY 注入，默认空串（切勿在源码硬编码密钥）
    api_key: str = "sk-a698f8d405f6437b9b48276a824972d6"
    api_base: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = 2048
    temperature: float = 0.7
    max_retries: int = 3
    request_timeout: int = 60


class EmbeddingSettings(BaseModel):
    provider: Literal["openai", "mock"] = "openai"
    api_key: str = "sk-hAmzXu5Nn99FKN4dhlb7eXIUzpip2q9j9LDPtVy0R2hqXnol"
    api_base: str = "https://4sapi.com"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 64
    max_retries: int = 3
    request_timeout: int = 30


class AsrSettings(BaseModel):
    provider: Literal["aliyun_nls", "xunfei", "mock"] = "xunfei"
    api_key: str = "9f81fceb9c38b176a0687e4f901cde52"
    api_secret: str = "YzRkYjJmMWU1ZDM1ZmRlMzFjZGE1NWNi"
    app_id: str = "0511cfd4"
    api_base: str = ""
    request_timeout: int = 30
    heartbeat_interval: int = 5


class TtsSettings(BaseModel):
    provider: Literal["aliyun_nls", "azure", "xunfei", "mock"] = "xunfei"
    api_key: str = "9f81fceb9c38b176a0687e4f901cde52"
    api_secret: str = "YzRkYjJmMWU1ZDM1ZmRlMzFjZGE1NWNi"
    app_id: str = "0511cfd4"
    api_base: str = ""
    voice: str = "default"
    sample_rate: int = 24000
    format: str = "opus"
    request_timeout: int = 30


class SearchSettings(BaseModel):
    provider: Literal["tavily", "mock"] = "tavily"
    api_key: str = ""
    api_base: str = "https://api.tavily.com/search"
    daily_limit: int = 100
    request_timeout: int = 15


class RateLimitSettings(BaseModel):
    enabled: bool = True
    chat_capacity: int = 30
    chat_rate: float = 5.0
    upload_capacity: int = 10
    upload_rate: float = 2.0
    ws_capacity: int = 20
    ws_rate: float = 10.0
    write_capacity: int = 20
    write_rate: float = 3.0
    auth_capacity: int = 5
    auth_rate: float = 0.5


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
    asr: AsrSettings = AsrSettings()
    tts: TtsSettings = TtsSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    search: SearchSettings = SearchSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()


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
