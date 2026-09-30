from flask import jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.extensions import db


class APIError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _flatten(messages, prefix: str = "") -> list[str]:
    parts: list[str] = []
    if isinstance(messages, dict):
        for key, value in messages.items():
            if key in {"json", "form", "query", "files", "path", "headers"}:
                parts.extend(_flatten(value, prefix))
                continue
            label = f"{prefix}.{key}" if prefix else str(key)
            parts.extend(_flatten(value, label))
        return parts
    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, str):
                parts.append(f"{prefix}: {item}" if prefix else item)
            else:
                parts.extend(_flatten(item, prefix))
        return parts
    text = str(messages)
    return [f"{prefix}: {text}" if prefix else text]


def _detail_from_http(error: HTTPException) -> str:
    if error.code == 413:
        return "Image exceeds the maximum file size."
    data = getattr(error, "data", None)
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message
        nested = data.get("messages") or data.get("errors")
        if nested:
            flat = _flatten(nested)
            if flat:
                return "; ".join(flat)
    if error.code == 404:
        return "Resource not found."
    return error.description or "Request failed."


def register_error_handlers(app) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        db.session.rollback()
        return jsonify({"detail": error.detail}), error.status_code

    @app.errorhandler(IntegrityError)
    def handle_integrity(_error: IntegrityError):
        db.session.rollback()
        return jsonify({"detail": "Request conflicts with an existing record."}), 409

    @app.errorhandler(HTTPException)
    def handle_http(error: HTTPException):
        response = jsonify({"detail": _detail_from_http(error)})
        response.status_code = error.code or 500
        return response

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        if isinstance(error, HTTPException):
            return handle_http(error)
        app.logger.exception("Unhandled server error")
        db.session.rollback()
        return jsonify({"detail": "Internal server error."}), 500
