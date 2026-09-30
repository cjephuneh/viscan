import hmac
import json
from datetime import date
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory

from .models import (
    DIAGNOSIS_METHODS, DIAGNOSIS_RESULTS, HIV_STATUSES, HPV_STATUSES, SCREENING_VERDICTS, SYMPTOMS,
    TREATMENTS, VIA_RESULTS, AIInterpretation, ClinicianAnnotation, DiagnosisRecord, Outcome, Patient,
    ViaImage, db,
)
from .services.metrics import compute_metrics
from .services.overlay import render_overlay
from .services.pipeline import PipelineError, analyze_image, build_response

api_bp = Blueprint("api", __name__)


class BadRequest(ValueError):
    pass


@api_bp.errorhandler(BadRequest)
@api_bp.errorhandler(PipelineError)
def _bad_request(exc):
    return jsonify(error=str(exc)), 400


@api_bp.errorhandler(413)
def _too_large(_exc):
    return jsonify(error="Image exceeds the 10 MB limit."), 413


@api_bp.before_request
def _require_api_key():
    expected = current_app.config.get("API_KEY")
    if not expected or request.endpoint == "api.health":
        return None
    provided = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(provided, expected):
        return jsonify(error="Invalid or missing X-API-Key header."), 401
    return None


def _choice(value, allowed, field, required=False):
    if value in (None, ""):
        if required:
            raise BadRequest(f"'{field}' is required.")
        return None
    if value not in allowed:
        raise BadRequest(f"'{field}' must be one of: {', '.join(allowed)}.")
    return value


def _int(value, field, lo=None, hi=None):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f"'{field}' must be an integer.") from None
    if (lo is not None and number < lo) or (hi is not None and number > hi):
        raise BadRequest(f"'{field}' must be between {lo} and {hi}.")
    return number


def _bool(value, field):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "y", "on"):
        return True
    if text in ("false", "no", "0", "n", "off"):
        return False
    raise BadRequest(f"'{field}' must be true or false.")


def _symptoms(values: list[str]) -> list[str]:
    items = [s.strip() for v in values for s in v.split(",") if s.strip()]
    for item in items:
        _choice(item, SYMPTOMS, "symptoms")
    return sorted(set(items))


def _date(value, field):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BadRequest(f"'{field}' must be an ISO date (YYYY-MM-DD).") from None


def _json_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest("Expected a JSON object body.")
    return body


def _get_or_404(model, obj_id):
    return db.get_or_404(model, obj_id, description=f"{model.__name__} {obj_id} not found.")


@api_bp.get("/health")
def health():
    cfg = current_app.config
    mode = cfg["INTERPRETER_MODE"]
    engine = "openai" if mode == "openai" or (mode == "auto" and cfg["OPENAI_API_KEY"]) else "heuristic"
    return jsonify(status="ok", engine=engine, model=cfg["OPENAI_MODEL"] if engine == "openai" else None)


@api_bp.post("/interpret")
def interpret():
    """Upload a VIA image (multipart field 'image') and get an AI interpretation."""
    file = request.files.get("image")
    if file is None or not file.filename:
        raise BadRequest("Upload the image in multipart field 'image'.")
    form = request.form
    fields = {
        "patient_external_id": form.get("patient_external_id"),
        "age": _int(form.get("age"), "age", 10, 100),
        "hiv_status": _choice(form.get("hiv_status"), HIV_STATUSES, "hiv_status"),
        "hpv_status": _choice(form.get("hpv_status"), HPV_STATUSES, "hpv_status"),
        "hpv_genotypes": form.get("hpv_genotypes"),
        "pregnant": _bool(form.get("pregnant"), "pregnant"),
        "parity": _int(form.get("parity"), "parity", 0, 25),
        "smoker": _bool(form.get("smoker"), "smoker"),
        "contraception": form.get("contraception"),
        "previously_treated": _bool(form.get("previously_treated"), "previously_treated"),
        "previous_screening_result": _choice(form.get("previous_screening_result"), VIA_RESULTS,
                                             "previous_screening_result"),
        "symptoms": _symptoms(form.getlist("symptoms")),
        "visit_date": _date(form.get("visit_date"), "visit_date"),
        "clinician_id": form.get("clinician_id"),
        "notes": form.get("notes"),
        "site": form.get("site"),
        "device": form.get("device"),
    }
    try:
        result = analyze_image(file.read(), fields)
    except PipelineError:
        raise
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Interpretation failed")
        return jsonify(error=f"Interpretation failed: {exc}"), 502
    return jsonify(result), 201


@api_bp.get("/interpretations/<int:interp_id>")
def get_interpretation(interp_id):
    interp = _get_or_404(AIInterpretation, interp_id)
    return jsonify(build_response(interp) | {"annotations": [a.to_dict() for a in interp.annotations]})


@api_bp.get("/interpretations/<int:interp_id>/overlay.png")
def get_overlay(interp_id):
    interp = _get_or_404(AIInterpretation, interp_id)
    png = render_overlay(Path(current_app.config["UPLOAD_DIR"]) / interp.image.filename, interp)
    return Response(png, mimetype="image/png")


@api_bp.get("/interpretations/<int:interp_id>/report")
def get_report(interp_id):
    """Printable clinical report (HTML)."""
    interp = _get_or_404(AIInterpretation, interp_id)
    return render_template("report.html", r=build_response(interp),
                           annotations=[a.to_dict() for a in interp.annotations],
                           patient=interp.image.patient.to_dict() if interp.image.patient else None)


@api_bp.get("/worklist")
def worklist():
    """Clinician triage queue: unreviewed cases, most suspicious and highest risk first."""
    verdict = _choice(request.args.get("verdict"), SCREENING_VERDICTS, "verdict")
    status = _choice(request.args.get("status", "pending"), ("pending", "reviewed", "disputed", "all"), "status")
    limit = _int(request.args.get("limit"), "limit", 1, 500) or 50
    query = AIInterpretation.query
    if status != "all":
        query = query.filter(AIInterpretation.review_status == status)
    if verdict:
        query = query.filter(AIInterpretation.screening_verdict == verdict)
    urgency_rank = db.case(
        (AIInterpretation.via_result == "SUSPICIOUS_FOR_CANCER", 0),
        (AIInterpretation.screening_verdict == "SUSPICIOUS", 1),
        (AIInterpretation.screening_verdict == "INDETERMINATE", 2),
        else_=3,
    )
    rows = query.order_by(urgency_rank, AIInterpretation.risk_score.desc().nulls_last(),
                          AIInterpretation.created_at).limit(limit).all()
    return jsonify([
        {
            "interpretation_id": i.id,
            "patient_external_id": i.image.patient.external_id if i.image.patient else None,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "screening_verdict": i.screening_verdict,
            "via_result": i.via_result,
            "risk_score": i.risk_score,
            "suspicion_level": i.suspicion_level,
            "confidence": i.confidence,
            "urgency": (i.recommendation or {}).get("urgency"),
            "action": (i.recommendation or {}).get("action"),
            "follow_up_due": i.follow_up_due.isoformat() if i.follow_up_due else None,
            "review_status": i.review_status,
            "links": {"self": f"/api/v1/interpretations/{i.id}", "report": f"/api/v1/interpretations/{i.id}/report"},
        }
        for i in rows
    ])


@api_bp.get("/images/<int:image_id>/file")
def get_image_file(image_id):
    image = _get_or_404(ViaImage, image_id)
    return send_from_directory(current_app.config["UPLOAD_DIR"], image.filename, mimetype=image.mime_type)


@api_bp.post("/interpretations/<int:interp_id>/annotations")
def annotate(interp_id):
    """Clinician confirms or corrects the AI result. This is the ground-truth feedback loop."""
    interp = _get_or_404(AIInterpretation, interp_id)
    body = _json_body()
    clinician_id = (body.get("clinician_id") or "").strip()
    if not clinician_id:
        raise BadRequest("'clinician_id' is required.")
    via_result = _choice(body.get("via_result"), VIA_RESULTS, "via_result", required=True)
    positions = body.get("lesion_clock_positions") or []
    if not isinstance(positions, list) or not all(isinstance(p, int) and 1 <= p <= 12 for p in positions):
        raise BadRequest("'lesion_clock_positions' must be a list of integers 1-12.")

    annotation = ClinicianAnnotation(
        image_id=interp.image_id,
        interpretation_id=interp.id,
        clinician_id=clinician_id,
        via_result=via_result,
        agrees_with_ai=via_result == interp.via_result,
        lesion_clock_positions=positions,
        transformation_zone_type=_choice(
            body.get("transformation_zone_type"), ("type_1", "type_2", "type_3"), "transformation_zone_type"
        ),
        notes=body.get("notes"),
    )
    db.session.add(annotation)
    interp.review_status = "reviewed" if annotation.agrees_with_ai else "disputed"
    db.session.commit()
    return jsonify(annotation.to_dict() | {"review_status": interp.review_status}), 201


@api_bp.post("/patients/<int:patient_id>/diagnoses")
def add_diagnosis(patient_id):
    patient = _get_or_404(Patient, patient_id)
    body = _json_body()
    image_id = _int(body.get("image_id"), "image_id")
    if image_id is not None:
        image = _get_or_404(ViaImage, image_id)
        if image.patient_id != patient.id:
            raise BadRequest("image_id does not belong to this patient.")
    record = DiagnosisRecord(
        patient_id=patient.id,
        image_id=image_id,
        method=_choice(body.get("method"), DIAGNOSIS_METHODS, "method", required=True),
        result=_choice(body.get("result"), DIAGNOSIS_RESULTS, "result", required=True),
        diagnosed_on=_date(body.get("diagnosed_on"), "diagnosed_on"),
        notes=body.get("notes"),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@api_bp.post("/patients/<int:patient_id>/outcomes")
def add_outcome(patient_id):
    patient = _get_or_404(Patient, patient_id)
    body = _json_body()
    outcome = Outcome(
        patient_id=patient.id,
        image_id=_int(body.get("image_id"), "image_id"),
        treatment=_choice(body.get("treatment"), TREATMENTS, "treatment") or "none",
        treated_on=_date(body.get("treated_on"), "treated_on"),
        follow_up_on=_date(body.get("follow_up_on"), "follow_up_on"),
        follow_up_result=_choice(body.get("follow_up_result"), VIA_RESULTS + DIAGNOSIS_RESULTS, "follow_up_result"),
        status=_choice(body.get("status"), ("open", "completed", "lost_to_follow_up"), "status") or "open",
        notes=body.get("notes"),
    )
    db.session.add(outcome)
    db.session.commit()
    return jsonify(outcome.to_dict()), 201


@api_bp.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    """Full longitudinal record: images, AI reads, clinician annotations, diagnoses, outcomes."""
    patient = _get_or_404(Patient, patient_id)
    return jsonify(
        patient.to_dict()
        | {
            "images": [
                img.to_dict() | {"interpretations": [i.to_dict() for i in img.interpretations]}
                for img in patient.images
            ],
            "visits": [v.to_dict() for v in patient.visits],
            "diagnoses": [d.to_dict() for d in patient.diagnoses],
            "outcomes": [o.to_dict() for o in patient.outcomes],
        }
    )


@api_bp.get("/metrics")
def metrics():
    return jsonify(compute_metrics())


@api_bp.get("/dataset/export")
def export_dataset():
    """JSONL export of every labelled image for audits, evaluation or future fine-tuning."""

    lines = []
    for image in ViaImage.query.order_by(ViaImage.id):
        patient = image.patient
        record = {
            "image_id": image.id,
            "file": image.filename,
            "sha256": image.sha256,
            "quality": image.quality,
            "patient": patient.to_dict() if patient else None,
            "ai": [
                {"id": i.id, "engine": i.engine, "model": i.model,
                 "via_result": i.via_result, "confidence": i.confidence}
                for i in image.interpretations
            ],
            "clinician_annotations": [a.to_dict() for a in image.annotations],
            "diagnoses": [d.to_dict() for d in patient.diagnoses] if patient else [],
            "outcomes": [o.to_dict() for o in patient.outcomes] if patient else [],
        }
        lines.append(json.dumps(record) + "\n")

    return Response("".join(lines), mimetype="application/x-ndjson",
                    headers={"Content-Disposition": "attachment; filename=viscan_dataset.jsonl"})
