from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError


def synthesize(text: str, language: str | None = None) -> dict[str, Any]:
    api_url = current_app.config.get("VOICE_API_URL") or ""
    api_key = current_app.config.get("VOICE_API_KEY") or ""
    if not api_url or not api_key:
        return {
            "status": "queued_locally",
            "provider": "stub",
            "text": text,
            "language": language,
            "detail": "Voice provider is not configured. Request accepted locally.",
        }

    timeout = current_app.config["EXTERNAL_TIMEOUT_SECONDS"]
    body: dict[str, Any] = {"text": text}
    if language:
        body["language"] = language

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                api_url.rstrip("/") + "/synthesize",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
            )
    except httpx.RequestError as exc:
        raise APIError("Voice provider is unavailable.", 503) from exc

    if response.status_code >= 400:
        raise APIError("Voice provider rejected the request.", 502)

    try:
        payload = response.json()
    except ValueError:
        payload = {"status": "accepted"}

    return {
        "status": "accepted",
        "provider": "configured",
        "text": text,
        "language": language,
        "response": payload,
    }
