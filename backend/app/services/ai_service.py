from __future__ import annotations

from typing import Any

import httpx
from flask import current_app

from app.errors import APIError
from app.services.http_client import shared_client

_REAL_CLIENT = httpx.Client

REQUIRED_KEYS = ("prediction", "confidence", "model_version", "processing_time_ms")
_VIA_RESULTS = {"VIA_NEGATIVE", "VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER", "INADEQUATE"}


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


def phase_targets() -> list[str]:
    """Interpreter URLs for each review phase. Later phases see the previous result."""
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
    """Send the stored VIA image to the interpreter and normalise its answer.

    ``image_url`` is kept for logging. The bytes are read from storage and posted
    as multipart, so the interpreter does not fetch them back from this API.
    A later phase sends the previous reading in the visit notes.
    """
    if not base_url:
        base_url = current_app.config["AI_API_URL"]
    timeout = current_app.config["AI_TIMEOUT_SECONDS"]
    url = f"{base_url.rstrip('/')}/api/v1/interpret"

    data, filename, media_type = _load_image(image_id)
    headers = {}
    if current_app.config.get("AI_API_KEY"):
        headers["X-API-Key"] = current_app.config["AI_API_KEY"]
    notes = f"backend image {image_id} ({image_url}). Review phase {phase}."
    form: dict[str, str] = {"site": "viscan-backend", "notes": notes}
    if prior:
        prediction = str(prior.get("prediction") or "").strip()
        confidence = prior.get("confidence")
        form["notes"] = (
            f"{notes} Previous reading: {prediction}"
            + (f" at confidence {confidence}." if confidence is not None else ".")
        )[:1000]
        if prediction in _VIA_RESULTS:
            form["previous_screening_result"] = prediction

    try:
        response = _post_image(url, data, filename, media_type, form, headers, timeout)
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


def _post_image(url, data, filename, media_type, form, headers, timeout):
    # Tests replace httpx.Client and expect a context manager. Production uses
    # the shared client so the next phase does not open a new connection.
    files = {"image": (filename, data, media_type)}
    if httpx.Client is not _REAL_CLIENT:
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, files=files, data=form, headers=headers)
    return shared_client().post(url, files=files, data=form, headers=headers, timeout=timeout)
