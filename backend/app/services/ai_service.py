from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError
from app.services.http_client import shared_client

_REAL_CLIENT = httpx.Client


REQUIRED_KEYS = ("prediction", "confidence", "model_version", "processing_time_ms")


def _validate_ai_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise APIError("AI service returned an invalid response.", 502)

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise APIError("AI service returned an incomplete response.", 502)

    prediction = payload["prediction"]
    confidence = payload["confidence"]
    model_version = payload["model_version"]
    processing_time_ms = payload["processing_time_ms"]

    if not isinstance(prediction, str) or not prediction.strip():
        raise APIError("AI service returned an invalid prediction.", 502)
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        raise APIError("AI service returned an invalid confidence value.", 502)
    if not isinstance(model_version, str) or not model_version.strip():
        raise APIError("AI service returned an invalid model version.", 502)
    if not isinstance(processing_time_ms, int) or processing_time_ms < 0:
        raise APIError("AI service returned an invalid processing time.", 502)

    recommendation = payload.get("recommendation")
    if recommendation is None or (isinstance(recommendation, str) and not recommendation.strip()):
        recommendation_text = None
    elif isinstance(recommendation, str):
        recommendation_text = recommendation.strip()[:1000]
    else:
        raise APIError("AI service returned an invalid recommendation.", 502)

    return {
        "prediction": prediction.strip(),
        "confidence": float(confidence),
        "model_version": model_version.strip(),
        "processing_time_ms": processing_time_ms,
        "recommendation": recommendation_text,
    }


def phase_targets() -> list[str]:
    """URLs for the analysis agency. Later phases review the previous result."""
    count = int(current_app.config.get("AI_PHASE_COUNT", 1))
    raw = (current_app.config.get("AI_PHASE_URLS") or "").strip()
    urls = [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
    fallback = current_app.config["AI_API_URL"].rstrip("/")
    if not urls:
        urls = [fallback]
    while len(urls) < count:
        urls.append(urls[-1])
    return urls[:count]


def analyze_image(
    image_url: str,
    image_id: int,
    *,
    phase: int = 1,
    prior: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    if not base_url:
        base_url = current_app.config["AI_API_URL"]
    timeout = current_app.config["AI_TIMEOUT_SECONDS"]
    url = f"{base_url.rstrip('/')}/predict"
    body: dict[str, Any] = {
        "image_url": image_url,
        "image_id": image_id,
        "phase": phase,
    }
    if prior:
        body["prior_result"] = {
            "prediction": prior.get("prediction"),
            "confidence": prior.get("confidence"),
            "model_version": prior.get("model_version"),
            "recommendation": prior.get("recommendation"),
            "phase": prior.get("phase", phase - 1),
        }

    try:
        response = _post_json(url, body, timeout)
    except httpx.TimeoutException as exc:
        raise APIError("AI service timed out.", 504) from exc
    except httpx.RequestError as exc:
        raise APIError("AI service is unavailable.", 503) from exc

    if response.status_code >= 500:
        raise APIError("AI service is unavailable.", 503)
    if response.status_code >= 400:
        raise APIError("AI service rejected the analysis request.", 502)

    try:
        payload = response.json()
    except ValueError as exc:
        raise APIError("AI service returned an invalid response.", 502) from exc

    return _validate_ai_payload(payload)


def _post_json(url: str, body: dict[str, Any], timeout: float):
    # Tests replace httpx.Client and expect a context manager. Production uses
    # the shared client so the next phase does not open a new connection.
    if httpx.Client is not _REAL_CLIENT:
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, json=body)
    return shared_client().post(url, json=body, timeout=timeout)
