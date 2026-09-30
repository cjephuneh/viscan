import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _database_uri() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.getenv("DB_HOST"):
        return URL.create(
            "postgresql+psycopg",
            username=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.environ["DB_HOST"],
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "viscan"),
            query={"sslmode": os.getenv("DB_SSLMODE", "prefer")},
        ).render_as_string(hide_password=False)
    return f"sqlite:///{os.getenv('SQLITE_PATH', BASE_DIR / 'instance' / 'viscan.db')}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "instance" / "uploads"))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
    OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "")
    INTERPRETER_MODE = os.getenv("INTERPRETER_MODE", "auto")
    FEWSHOT_EXAMPLES = int(os.getenv("FEWSHOT_EXAMPLES", "2"))
    REVIEW_CONFIDENCE_THRESHOLD = float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.75"))

    API_KEY = os.getenv("VISCAN_API_KEY", "")

    DEFAULT_LATITUDE = float(os.getenv("DEFAULT_LATITUDE", "-1.9441"))
    DEFAULT_LONGITUDE = float(os.getenv("DEFAULT_LONGITUDE", "30.0619"))
    OVERPASS_URLS = os.getenv(
        "OVERPASS_URLS",
        "https://overpass-api.de/api/interpreter,https://overpass.kumi.systems/api/interpreter",
    ).split(",")
    SEED_DEMO_PARTNERS = os.getenv("SEED_DEMO_PARTNERS", "1") == "1"

    ANAM_API_KEY = os.getenv("ANAM_API_KEY", "")
    ANAM_BASE_URL = os.getenv("ANAM_BASE_URL", "https://api.anam.ai/v1")
    ANAM_PERSONA_ID = os.getenv("ANAM_PERSONA_ID", "34584421-e431-4c3e-b7c5-eece5793a7dc")
    # GPT 4.1 Mini: reliable client-tool calling. The persona's default (GPT OSS 120B) leaks tool calls as text.
    ANAM_LLM_ID = os.getenv("ANAM_LLM_ID", "0934d97d-0c3a-4f33-91b0-5e136a0ef466")
    ANAM_MAX_SESSION_SECONDS = int(os.getenv("ANAM_MAX_SESSION_SECONDS", "900"))
