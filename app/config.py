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
