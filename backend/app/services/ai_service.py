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


def _from_interpreter_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map the ai-interpreter ``POST /api/v1/interpret`` response onto the
    flat ``{prediction, confidence, model_version, processing_time_ms,
    recommendation}`` shape stored in ``AIResult``."""
    verdict = payload.get("verdict") or payload.get("diagnosis") or {}
    engine = payload.get("engine") or {}
    rec = payload.get("recommendation") or {}

    name = engine.get("name") or "ai-interpreter"
    model = engine.get("model")
    model_version = f"{name}/{model}" if model else str(name)

    latency = engine.get("latency_ms")
    if not isinstance(latency, int) or isinstance(latency, bool) or latency < 0:
        latency = 0

    recommendation = None
    if isinstance(rec, dict):
        action, urgency = rec.get("action"), rec.get("urgency")
        recommendation = f"{action} (urgency: {urgency})" if action and urgency else (action or None)
    elif isinstance(rec, str):
        recommendation = rec

    return _validate_ai_payload({
        "prediction": verdict.get("via_result") or payload.get("via_result"),
        "confidence": verdict.get("confidence", payload.get("confidence")),
        "model_version": model_version[:64],
        "processing_time_ms": latency,
        "recommendation": recommendation,
    })


def _load_image(image_id: int) -> tuple[bytes, str, str]:
    from app.extensions import db
    from app.models import VIAImage
    from app.utils.images import load_image_bytes

    image = db.session.get(VIAImage, image_id)
    if image is None:
        raise APIError("Image not found.", 404)
    data = load_image_bytes(image.file_path)
    filename = image.file_path.rsplit("/", 1)[-1]
    return data, filename, image.media_type


def analyze_image(image_url: str, image_id: int) -> dict[str, Any]:
    """Send the stored VIA image to the AI interpreter and normalise its answer.

    ``image_url`` is kept for logging/back-compat; the bytes are read from blob
    storage and posted as multipart, so the AI service never has to fetch
    anything back from this API.
    """
    base_url = current_app.config["AI_API_URL"].rstrip("/")
    timeout = current_app.config["AI_TIMEOUT_SECONDS"]
    url = f"{base_url}/api/v1/interpret"

    data, filename, media_type = _load_image(image_id)
    headers = {}
    if current_app.config.get("AI_API_KEY"):
        headers["X-API-Key"] = current_app.config["AI_API_KEY"]
    form = {"site": "viscan-backend", "notes": f"backend image {image_id} ({image_url})"}

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                files={"image": (filename, data, media_type)},
                data=form,
                headers=headers,
            )
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

    if isinstance(payload, dict) and "interpretation_id" in payload:
        return _from_interpreter_payload(payload)
    return _validate_ai_payload(payload)
