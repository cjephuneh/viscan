from __future__ import annotations

from typing import Any

from app.errors import APIError
from app.models import AIResult, Screening
from app.services import sms_service, whatsapp_service

POSITIVE_LABELS = frozenset(
    {
        "abnormal",
        "positive",
        "via_positive",
        "suspicious",
        "high_risk",
    }
)

DEFAULT_POSITIVE_RECOMMENDATION = (
    "Please return to your health facility for follow-up. "
    "Further evaluation may be needed."
)


def is_positive_label(label: str | None) -> bool:
    if not label:
        return False
    return label.strip().lower().replace(" ", "_") in POSITIVE_LABELS


def latest_ai_result(screening: Screening) -> AIResult | None:
    for image in reversed(list(screening.images or [])):
        results = list(image.ai_results or [])
        if results:
            return results[-1]
    return None


def build_assessment_message(screening: Screening) -> str:
    assessment = screening.assessment
    if assessment is None:
        raise APIError("Assessment is required before notifying the patient.", 400)

    result = assessment.result.strip()
    lines = [
        f"VISCAN update for screening {screening.patient_code}.",
        f"Clinician result: {result}.",
    ]

    if is_positive_label(result):
        ai_result = latest_ai_result(screening)
        recommendation = None
        if ai_result is not None and ai_result.recommendation:
            recommendation = ai_result.recommendation.strip()
        if not recommendation:
            recommendation = DEFAULT_POSITIVE_RECOMMENDATION
        lines.append(f"Recommendation: {recommendation}")

    return " ".join(lines)


def notify_patient(screening: Screening) -> dict[str, Any]:
    phone = (screening.phone or "").strip()
    channel = (screening.notify_channel or "").strip().lower()
    if not phone or not channel:
        raise APIError(
            "Screening needs phone and notify_channel before the patient can be notified.",
            400,
        )
    if channel not in ("sms", "whatsapp"):
        raise APIError("notify_channel must be sms or whatsapp.", 400)

    message = build_assessment_message(screening)
    if channel == "sms":
        delivery = sms_service.send_sms(to=phone, message=message)
    else:
        delivery = whatsapp_service.send_whatsapp(to=phone, message=message)

    return {
        "screening_id": screening.id,
        "channel": channel,
        "to": phone,
        "message": message,
        "positive": is_positive_label(
            screening.assessment.result if screening.assessment else None
        ),
        "delivery": delivery,
    }
