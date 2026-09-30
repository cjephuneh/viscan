from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "ViScan Cervical AI Avatar Service"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9090
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "*"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Remote PostgreSQL Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/viscan_avatar"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Anam AI Configuration
    ANAM_API_KEY: str = ""
    ANAM_BASE_URL: str = "https://api.anam.ai/v1"
    ANAM_DEFAULT_PERSONA_ID: str = ""
    ANAM_DEFAULT_AVATAR_ID: str = ""
    ANAM_DEFAULT_VOICE_ID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
