from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError


def translate(text: str, source_language: str, target_language: str) -> dict[str, Any]:
    api_url = current_app.config.get("LANGUAGE_API_URL") or ""
    api_key = current_app.config.get("LANGUAGE_API_KEY") or ""
    if not api_url or not api_key:
        return {
            "translated_text": text,
            "source_language": source_language,
            "target_language": target_language,
            "provider": "stub",
            "detail": "Language provider is not configured. Original text returned.",
        }

    timeout = current_app.config["EXTERNAL_TIMEOUT_SECONDS"]
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                api_url.rstrip("/") + "/translate",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "text": text,
                    "source_language": source_language,
                    "target_language": target_language,
                },
            )
    except httpx.RequestError as exc:
        raise APIError("Language provider is unavailable.", 503) from exc

    if response.status_code >= 400:
        raise APIError("Language provider rejected the request.", 502)

    try:
        payload = response.json()
    except ValueError as exc:
        raise APIError("Language provider returned an invalid response.", 502) from exc

    translated = payload.get("translated_text")
    if not isinstance(translated, str):
        raise APIError("Language provider returned an invalid response.", 502)

    return {
        "translated_text": translated,
        "source_language": source_language,
        "target_language": target_language,
        "provider": "configured",
    }
