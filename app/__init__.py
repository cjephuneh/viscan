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
        if app.config["SEED_DEMO_PARTNERS"]:
            from .services.care import seed_demo_partners

            seed_demo_partners(app.config["DEFAULT_LATITUDE"], app.config["DEFAULT_LONGITUDE"])

    return app
