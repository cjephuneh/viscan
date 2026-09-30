from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError


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


def analyze_image(image_url: str, image_id: int) -> dict[str, Any]:
    base_url = current_app.config["AI_API_URL"].rstrip("/")
    timeout = current_app.config["AI_TIMEOUT_SECONDS"]
    url = f"{base_url}/predict"
    body = {"image_url": image_url, "image_id": image_id}

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=body)
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
