from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db

blp = Blueprint("health", __name__, url_prefix="/api/v1/health")


@blp.get("/")
def health():
    database = "disconnected"
    try:
        db.session.execute(text("SELECT 1"))
        database = "connected"
    except Exception:
        current_app.logger.exception("Database health check failed")
        database = "disconnected"

    status = "ok" if database == "connected" else "degraded"
    code = 200 if database == "connected" else 503
    return jsonify({"status": status, "database": database}), code
