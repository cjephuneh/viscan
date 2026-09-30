"""Clinician video report via the ai-avatar service.

Once a clinician has confirmed (or corrected) an AI reading, the *approved*
result is sent to ai-avatar (``POST /api/v1/reports``), which writes the
narration script and renders an avatar video with Anam. The frontend then
embeds ``/player/<scan_id>`` in an iframe.

The report is identified by a deterministic ``scan_id`` derived from the
interpretation id, so no extra column is needed here and the frontend can
address the report directly:  ``viscan-<interpretation_id>``.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

RESULT_LABELS = {
    "VIA_NEGATIVE": "VIA negative - no acetowhite lesion (NILM equivalent)",
    "VIA_POSITIVE": "VIA positive - acetowhite lesion present",
    "SUSPICIOUS_FOR_CANCER": "Suspicious for invasive cervical cancer",
    "INADEQUATE": "Inadequate image - screening must be repeated",
}
TZ_LABELS = {
    "type_1": "Type 1 - Fully visible",
    "type_2": "Type 2 - Partially endocervical, fully visible",
    "type_3": "Type 3 - Not fully visible",
}


def scan_id_for(interpretation_id: int) -> str:
    return f"viscan-{interpretation_id}"


def _humanize(value: str | None) -> str | None:
    return value.replace("_", " ") if value else None


def _clock(positions) -> str | None:
    positions = sorted({int(p) for p in (positions or []) if isinstance(p, int)})
    if not positions:
        return None
    if len(positions) == 1:
        return f"{positions[0]} o'clock"
    contiguous = positions[-1] - positions[0] == len(positions) - 1
    if contiguous:
        return f"{positions[0]} to {positions[-1]} o'clock"
    return ", ".join(str(p) for p in positions) + " o'clock"


def build_report_payload(interp, annotation) -> dict:
    """Map an interpretation + the clinician's annotation onto ai-avatar's ReportCreateRequest."""
    ai = interp.findings or {}
    findings = ai.get("findings") or {}
    rec = interp.recommendation or {}
    image = interp.image
    patient = image.patient if image is not None else None

    approved = annotation.via_result
    if annotation.agrees_with_ai:
        review = f"Clinician {annotation.clinician_id} confirmed the AI reading ({approved})."
    else:
        review = (f"Clinician {annotation.clinician_id} corrected the AI reading "
                  f"from {interp.via_result} to {approved}.")
    notes = " ".join(p for p in (review, (annotation.notes or "").strip()) if p)

    lesions = list(interp.lesions or [])
    vessels = sorted({_humanize(l.vessel_pattern) for l in lesions if getattr(l, "vessel_pattern", None)})
    aceto_parts = [_humanize(findings.get("acetowhite_density")),
                   findings.get("lesion_margins") and f"{_humanize(findings['lesion_margins'])} margins"]
    if findings.get("cervix_area_involved_percent") is not None:
        aceto_parts.append(f"about {findings['cervix_area_involved_percent']}% of the cervix")
    aceto = ", ".join(p for p in aceto_parts if p) if findings.get("acetowhite_present") else "No significant acetowhite change"

    observations = list(ai.get("key_observations") or [])
    if ai.get("rationale"):
        observations.append(ai["rationale"])

    action = rec.get("action") or "Follow the national cervical screening guideline."
    urgency = rec.get("urgency")
    recommendations = f"{action} (urgency: {urgency})" if urgency else action

    payload = {
        "scan_id": scan_id_for(interp.id),
        "patient_id": (patient.external_id if patient is not None and patient.external_id else
                       f"patient-{image.patient_id}" if image is not None and image.patient_id else
                       f"visit-{image.visit_id}" if image is not None and image.visit_id else "anonymous"),
        "clinician_id": annotation.clinician_id,
        "screening_result": RESULT_LABELS.get(approved, approved),
        "confidence_score": max(0.0, min(1.0, float(interp.confidence))) if interp.confidence is not None else None,
        "findings": {
            "transformation_zone": TZ_LABELS.get(annotation.transformation_zone_type
                                                 or ai.get("transformation_zone_type") or "", None),
            "aceto_white_changes": aceto,
            "lesion_quadrant": _clock(annotation.lesion_clock_positions or findings.get("lesion_clock_positions")),
            "vascular_patterns": ", ".join(vessels) if vessels else None,
            "lugol_iodine_reaction": None,
            "additional_observations": " ".join(observations)[:1000] or None,
        },
        "recommendations": recommendations[:1000],
        "clinical_notes": notes[:1000] or None,
    }
    return payload


class VideoReportError(RuntimeError):
    pass


def _post_json(url: str, body: dict, timeout: int) -> tuple[int, dict]:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        return exc.code, {"detail": detail}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VideoReportError(f"Could not reach the avatar service: {exc}") from exc


def create_video_report(cfg, payload: dict) -> dict:
    """Synchronously create the report on ai-avatar. Idempotent on scan_id (409 = already there)."""
    base = (cfg.get("AVATAR_API_URL") or "").rstrip("/")
    if not base:
        raise VideoReportError("AVATAR_API_URL is not configured.")
    status, data = _post_json(f"{base}/api/v1/reports", payload, int(cfg.get("AVATAR_TIMEOUT_SECONDS", 60)))
    if status == 409:
        return {"scan_id": payload["scan_id"], "status": "exists"}
    if status >= 400:
        raise VideoReportError(f"Avatar service returned {status}: {data.get('detail')}")
    return data


def request_video_report(app, interp, annotation) -> dict:
    """Kick off the report for a confirmed reading.

    Returns ``{"scan_id", "status"}`` where status is one of
    ``disabled`` (no AVATAR_API_URL), ``requested`` (sent in the background),
    ``created`` / ``exists`` / ``failed`` (synchronous mode, used in tests).
    """
    cfg = app.config
    scan_id = scan_id_for(interp.id)
    if not cfg.get("AVATAR_API_URL"):
        return {"scan_id": scan_id, "status": "disabled"}

    payload = build_report_payload(interp, annotation)

    def _send() -> dict:
        try:
            data = create_video_report(cfg, payload)
            status = data.get("status") if data.get("status") == "exists" else "created"
            app.logger.info("video report %s %s", scan_id, status)
            return {"scan_id": scan_id, "status": status}
        except VideoReportError as exc:
            app.logger.warning("video report %s failed: %s", scan_id, exc)
            return {"scan_id": scan_id, "status": "failed", "error": str(exc)}

    if cfg.get("TESTING") or cfg.get("AVATAR_SYNC"):
        return _send()

    # The avatar service talks to Anam (a few seconds); don't hold the clinician's request.
    threading.Thread(target=_send, name=f"video-report-{scan_id}", daemon=True).start()
    return {"scan_id": scan_id, "status": "requested"}
