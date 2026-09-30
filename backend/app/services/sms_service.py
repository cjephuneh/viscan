from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError


def send_sms(to: str, message: str) -> dict[str, Any]:
    api_url = current_app.config.get("SMS_API_URL") or ""
    api_key = current_app.config.get("SMS_API_KEY") or ""
    if not api_url or not api_key:
        return {
            "status": "queued_locally",
            "provider": "stub",
            "to": to,
            "message": message,
            "detail": "SMS provider is not configured. Message accepted locally.",
        }

    timeout = current_app.config["EXTERNAL_TIMEOUT_SECONDS"]
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                api_url.rstrip("/") + "/sms",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"to": to, "message": message},
            )
    except httpx.RequestError as exc:
        raise APIError("SMS provider is unavailable.", 503) from exc

    if response.status_code >= 400:
        raise APIError("SMS provider rejected the request.", 502)

    try:
        payload = response.json()
    except ValueError:
        payload = {"status": "sent"}

    return {"status": "sent", "provider": "configured", "to": to, "response": payload}
