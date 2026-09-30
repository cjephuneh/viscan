from pathlib import Path

from flask import Flask

from .config import Config
from .models import db


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from .api import api_bp
    from .web import web_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(web_bp)

    with app.app_context():
        db.create_all()
        _ensure_columns(db)
        if app.config["SEED_DEMO_PARTNERS"]:
            from .services.care import seed_demo_partners

            seed_demo_partners(app.config["DEFAULT_LATITUDE"], app.config["DEFAULT_LONGITUDE"])

    return app


# Columns added after the first release. create_all() only creates missing
# tables, so existing databases get them here (idempotent).
_ADDED_COLUMNS = (
    ("via_image", "capture", "VARCHAR(32)"),
)


def _ensure_columns(database):
    from sqlalchemy import inspect, text

    inspector = inspect(database.engine)
    for table, column, ddl_type in _ADDED_COLUMNS:
        if table in inspector.get_table_names() and column not in {c["name"] for c in inspector.get_columns(table)}:
            with database.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
