import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.pool import StaticPool

load_dotenv()


def build_database_url() -> str:
    """Build a psycopg URL. An explicit DATABASE_URL overrides DB_* parts."""
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        return explicit

    user = quote_plus(os.getenv("DB_USER", "dev_user"))
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "viscan")
    sslmode = os.getenv("DB_SSLMODE", "disable").strip().lower()
    if sslmode in ("off", "false", "0", "none", ""):
        sslmode = "disable"
    return (
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
        f"?sslmode={sslmode}"
    )


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    API_TITLE = "VISCAN API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"
    OPENAPI_URL_PREFIX = "/api/v1"
    OPENAPI_JSON_PATH = "openapi.json"
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    API_SPEC_OPTIONS = {
        "info": {
            "description": (
                "VISCAN Flask API for screening records, VIA images, "
                "AI analysis, clinician assessment, and external integrations. "
                "The frontend calls this API only. Clinical labels are stored "
                "as supplied by the AI service or the clinician."
            )
        }
    }

    PORT = int(os.getenv("PORT", "8080"))
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")
    AI_API_URL = os.getenv("AI_API_URL", "http://localhost:8000")
    AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))
    EXTERNAL_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_TIMEOUT_SECONDS", "30"))

    MAPS_API_KEY = os.getenv("MAPS_API_KEY", "")
    MAPS_API_URL = os.getenv("MAPS_API_URL", "")
    SMS_API_KEY = os.getenv("SMS_API_KEY", "")
    SMS_API_URL = os.getenv("SMS_API_URL", "")
    WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")
    WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
    LANGUAGE_API_KEY = os.getenv("LANGUAGE_API_KEY", "")
    LANGUAGE_API_URL = os.getenv("LANGUAGE_API_URL", "")
    VOICE_API_KEY = os.getenv("VOICE_API_KEY", "")
    VOICE_API_URL = os.getenv("VOICE_API_URL", "")

    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = build_database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 10},
    }


class ProductionConfig(DevelopmentConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    AI_API_URL = "http://ai.test"
    PUBLIC_BASE_URL = "http://localhost:8080"
    AI_TIMEOUT_SECONDS = 5
    EXTERNAL_TIMEOUT_SECONDS = 5
    MAPS_API_KEY = ""
    MAPS_API_URL = ""
    SMS_API_KEY = ""
    SMS_API_URL = ""
    WHATSAPP_API_KEY = ""
    WHATSAPP_API_URL = ""
    LANGUAGE_API_KEY = ""
    LANGUAGE_API_URL = ""
    VOICE_API_KEY = ""
    VOICE_API_URL = ""


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
