import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from app.config import CONFIGS
from app.errors import register_error_handlers
from app.extensions import api, db, migrate
from app.routes import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    config_key = config_name or os.getenv("FLASK_CONFIG", "development")
    config_cls = CONFIGS[config_key]

    app = Flask(__name__)
    app.config.from_object(config_cls)
    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_UPLOAD_BYTES"]

    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    if not upload_folder.is_absolute():
        upload_folder = Path(app.root_path).parent / upload_folder
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_folder)

    origins = app.config["CORS_ORIGINS"]
    if origins == "*":
        CORS(app)
    else:
        CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in origins.split(",") if o.strip()]}})

    db.init_app(app)
    migrate.init_app(app, db)
    api.init_app(app)
    register_error_handlers(app)
    register_blueprints(api, app)

    # Ensure models are imported for metadata / migrations.
    from app import models  # noqa: F401

    @app.cli.command("seed-facilities")
    def seed_facilities():
        """Seed District Hospital and Health Centre if missing."""
        from app.models import Facility

        defaults = [
            {"name": "District Hospital", "type": "District Hospital"},
            {"name": "Health Centre", "type": "Health Centre"},
        ]
        created = 0
        for item in defaults:
            exists = Facility.query.filter_by(name=item["name"]).first()
            if exists is None:
                db.session.add(Facility(name=item["name"], type=item["type"], is_active=True))
                created += 1
        db.session.commit()
        print(f"Seeded {created} facilities.")

    return app
