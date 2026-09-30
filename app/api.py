import hmac
import json
from datetime import date
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory

from .models import (
    DIAGNOSIS_METHODS, DIAGNOSIS_RESULTS, HIV_STATUSES, HPV_STATUSES, SCREENING_VERDICTS, SYMPTOMS,
    TREATMENTS, VIA_RESULTS, AIInterpretation, ClinicianAnnotation, CoachSession, DiagnosisRecord, IntakeSession, Notification,
    Outcome, PartnerHospital, Patient, Referral, ViaImage, db,
)
from .services.avatar import AvatarUnavailable, create_session_token, fetch_persona
from .services import coach
from .services.history import HistoryError, list_screenings
from .services.care import compose_message, final_result, suggested_supplies
from .services.intake import IntakeError, apply_event, create_intake, intake_payload
from .services.metrics import compute_metrics
from .services.places import PlacesUnavailable, haversine_km, nearby_pharmacies
from .services.overlay import render_overlay
from .services.pipeline import PipelineError, analyze_image, build_response

api_bp = Blueprint("api", __name__)


class BadRequest(ValueError):
    pass


@api_bp.errorhandler(BadRequest)
@api_bp.errorhandler(PipelineError)
@api_bp.errorhandler(IntakeError)
@api_bp.errorhandler(coach.CoachError)
@api_bp.errorhandler(HistoryError)
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
    intake_id = _int(form.get("intake_id"), "intake_id")
    intake = _get_or_404(IntakeSession, intake_id) if intake_id else None
    try:
        result = analyze_image(file.read(), fields)
    except PipelineError:
        raise
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Interpretation failed")
        return jsonify(error=f"Interpretation failed: {exc}"), 502
    if intake:
        intake.interpretation_id = result["interpretation_id"]
        intake.patient_id = result["patient_id"]
        intake.visit_id = result["visit_id"]
        db.session.commit()
        result["intake_id"] = intake.id
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


@api_bp.get("/images/<int:image_id>/thumb.jpg")
def get_image_thumbnail(image_id):
    """Small JPEG preview (max 320 px), cached next to the uploads."""
    from PIL import Image

    image = _get_or_404(ViaImage, image_id)
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    thumb = upload_dir / "thumbs" / f"{image.id}.jpg"
    if not thumb.exists():
        thumb.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(upload_dir / image.filename) as img:
            img = img.convert("RGB")
            img.thumbnail((320, 320))
            img.save(thumb, "JPEG", quality=80)
    return send_from_directory(thumb.parent, thumb.name, mimetype="image/jpeg", max_age=86400)


@api_bp.get("/screenings")
def screenings():
    """Past screenings, newest first. Filters: q, verdict, status, from, to, referred, overdue;
    sort (newest, oldest, risk); page, per_page. Includes headline totals in 'summary'."""
    return jsonify(list_screenings(request.args))


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


def _coords():
    cfg = current_app.config
    try:
        lat = float(request.args.get("lat", cfg["DEFAULT_LATITUDE"]))
        lng = float(request.args.get("lng", cfg["DEFAULT_LONGITUDE"]))
    except ValueError:
        raise BadRequest("'lat' and 'lng' must be numbers.") from None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise BadRequest("'lat'/'lng' out of range.")
    return lat, lng


@api_bp.get("/places/pharmacies")
def pharmacies():
    """Pharmacies near a location, from OpenStreetMap."""
    lat, lng = _coords()
    radius = _int(request.args.get("radius"), "radius", 200, 20000) or 3000
    try:
        places = nearby_pharmacies(lat, lng, radius, current_app.config["OVERPASS_URLS"])
    except PlacesUnavailable as exc:
        return jsonify(error=str(exc), source="openstreetmap", results=[]), 503
    return jsonify(source="openstreetmap", center={"lat": lat, "lng": lng}, radius_m=radius, results=places)


@api_bp.get("/partner-hospitals")
def list_partner_hospitals():
    lat, lng = _coords()
    service = request.args.get("service")
    rows = []
    for hospital in PartnerHospital.query.filter_by(accepts_referrals=True).all():
        if service and service not in (hospital.services or []):
            continue
        rows.append(hospital.to_dict(haversine_km(lat, lng, hospital.latitude, hospital.longitude)))
    rows.sort(key=lambda h: h["distance_km"])
    return jsonify(center={"lat": lat, "lng": lng}, results=rows)


@api_bp.post("/partner-hospitals")
def create_partner_hospital():
    body = _json_body()
    name = (body.get("name") or "").strip()
    if not name:
        raise BadRequest("'name' is required.")
    try:
        lat, lng = float(body["latitude"]), float(body["longitude"])
    except (KeyError, TypeError, ValueError):
        raise BadRequest("'latitude' and 'longitude' are required numbers.") from None
    services = body.get("services") or []
    if not isinstance(services, list):
        raise BadRequest("'services' must be a list of strings.")
    hospital = PartnerHospital(
        name=name, address=body.get("address"), city=body.get("city"), phone=body.get("phone"),
        whatsapp=body.get("whatsapp"), latitude=lat, longitude=lng, services=services,
        opening_hours=body.get("opening_hours"), accepts_referrals=body.get("accepts_referrals", True),
        is_demo=False,
    )
    db.session.add(hospital)
    db.session.commit()
    return jsonify(hospital.to_dict()), 201


@api_bp.get("/interpretations/<int:interp_id>/care")
def care_summary(interp_id):
    """What happens after this screen: referral need, suggested supplies, referrals and messages so far."""
    interp = _get_or_404(AIInterpretation, interp_id)
    via_result, source = final_result(interp)
    rec = interp.recommendation or {}
    patient = interp.image.patient
    return jsonify(
        interpretation_id=interp.id,
        patient_external_id=patient.external_id if patient else None,
        final_via_result=via_result,
        result_source=source,
        screening_verdict=interp.screening_verdict,
        is_suspicious=via_result in ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"),
        needs_referral=via_result == "SUSPICIOUS_FOR_CANCER" or rec.get("ablation_eligible") is False,
        urgency=rec.get("urgency"),
        action=rec.get("action"),
        suggested_supplies=suggested_supplies(via_result, rec, interp.findings or {}),
        referrals=[r.to_dict() for r in Referral.query.filter_by(interpretation_id=interp.id).order_by(Referral.created_at)],
        notifications=[n.to_dict() for n in Notification.query.filter_by(interpretation_id=interp.id).order_by(Notification.created_at)],
        message_preview={ch: compose_message(interp, ch, _latest_referral_hospital(interp.id)) for ch in ("sms", "whatsapp")},
    )


def _latest_referral_hospital(interp_id):
    referral = Referral.query.filter_by(interpretation_id=interp_id).order_by(Referral.created_at.desc()).first()
    return referral.hospital if referral else None


@api_bp.post("/interpretations/<int:interp_id>/referrals")
def create_referral(interp_id):
    interp = _get_or_404(AIInterpretation, interp_id)
    body = _json_body()
    hospital_id = _int(body.get("hospital_id"), "hospital_id")
    if hospital_id is None:
        raise BadRequest("'hospital_id' is required.")
    hospital = _get_or_404(PartnerHospital, hospital_id)
    referral = Referral(
        interpretation_id=interp.id,
        patient_id=interp.image.patient_id,
        hospital_id=hospital.id,
        reason=body.get("reason") or (interp.recommendation or {}).get("action"),
        urgency=_choice(body.get("urgency"), ("routine", "soon", "urgent"), "urgency")
        or (interp.recommendation or {}).get("urgency"),
        referred_by=body.get("referred_by"),
        status="sent",
    )
    db.session.add(referral)
    db.session.commit()
    return jsonify(referral.to_dict()), 201


@api_bp.post("/interpretations/<int:interp_id>/notifications")
def send_notification(interp_id):
    """Send the patient their result by SMS or WhatsApp. Currently a dummy provider: stored, not sent."""
    interp = _get_or_404(AIInterpretation, interp_id)
    body = _json_body()
    channel = _choice(body.get("channel"), ("sms", "whatsapp"), "channel", required=True)
    recipient = "".join(ch for ch in str(body.get("phone") or "") if ch.isdigit() or ch == "+")
    if len(recipient.lstrip("+")) < 7:
        raise BadRequest("'phone' must be a valid phone number.")
    message = (body.get("message") or "").strip() or compose_message(
        interp, channel, _latest_referral_hospital(interp.id))
    notification = Notification(
        interpretation_id=interp.id,
        patient_id=interp.image.patient_id,
        channel=channel,
        recipient=recipient,
        message=message[:1000],
        status="simulated",
        provider="dummy",
        sent_by=body.get("sent_by"),
    )
    db.session.add(notification)
    db.session.commit()
    return jsonify(notification.to_dict()), 201


@api_bp.post("/intake")
def start_intake():
    """Start a pre-screening intake (the patient meets the avatar, or fills the form)."""
    body = request.get_json(silent=True) or {}
    intake = create_intake(language=body.get("language"), channel=body.get("channel") or "avatar")
    return jsonify(intake_payload(intake)), 201


@api_bp.get("/intake")
def list_intakes():
    """Waiting room: recent intakes, newest first."""
    query = IntakeSession.query
    status = _choice(request.args.get("status"), ("in_progress", "completed"), "status")
    if status:
        query = query.filter_by(status=status)
    if request.args.get("unscreened") in ("1", "true"):
        query = query.filter(IntakeSession.interpretation_id.is_(None))
    limit = _int(request.args.get("limit"), "limit", 1, 200) or 50
    rows = query.order_by(IntakeSession.created_at.desc()).limit(limit).all()
    return jsonify([intake_payload(row) for row in rows])


@api_bp.get("/intake/<int:intake_id>")
def get_intake(intake_id):
    intake = _get_or_404(IntakeSession, intake_id)
    return jsonify(intake_payload(intake, include_transcript=request.args.get("transcript") in ("1", "true")))


@api_bp.get("/intake/code/<code>")
def get_intake_by_code(code):
    intake = IntakeSession.query.filter_by(code=code.strip().upper()).first()
    if intake is None:
        return jsonify(error=f"No intake with code {code}."), 404
    return jsonify(intake_payload(intake))


@api_bp.get("/avatar/persona")
def avatar_persona():
    """Public details of the intake avatar (name, portrait) and whether it can be started."""
    try:
        persona = fetch_persona(current_app.config)
    except AvatarUnavailable as exc:
        current_app.logger.warning("Avatar unavailable: %s", exc)
        return jsonify(available=False, name="Mia", image_url=None)
    return jsonify(available=True, name=persona["name"], image_url=persona["image_url"])


@api_bp.post("/intake/<int:intake_id>/avatar-token")
def intake_avatar_token(intake_id):
    """Short-lived Anam session token for the avatar; the API key never leaves the server."""
    intake = _get_or_404(IntakeSession, intake_id)
    try:
        token = create_session_token(current_app.config, client_label=f"viscan-intake-{intake.code}")
    except AvatarUnavailable as exc:
        current_app.logger.warning("Avatar unavailable: %s", exc)
        return jsonify(error=str(exc)), 503
    return jsonify(token)


@api_bp.post("/intake/<int:intake_id>/events")
def intake_event(intake_id):
    """Record something the avatar learned: {type, data}. Types: details, answer, feeling, concern,
    question, topic, breathing, finish, transcript."""
    intake = _get_or_404(IntakeSession, intake_id)
    body = _json_body()
    if body.get("anam_session_id"):
        intake.anam_session_id = str(body["anam_session_id"])[:64]
    message = apply_event(intake, body.get("type"), body.get("data") or {})
    db.session.commit()
    return jsonify(message=message, intake=intake_payload(intake))


@api_bp.get("/coach/persona")
def coach_persona():
    """Public details of the clinical coach avatar and whether it can be started."""
    try:
        persona = coach.coach_persona(current_app.config)
    except AvatarUnavailable as exc:
        current_app.logger.warning("Coach unavailable: %s", exc)
        return jsonify(available=False, name=current_app.config.get("ANAM_COACH_NAME") or "Kezia", image_url=None)
    return jsonify(available=bool(current_app.config.get("ANAM_API_KEY")), **persona)


@api_bp.post("/coach/sessions")
def start_coach_session():
    """Start a lesson: {interpretation_id?, clinician_id?}. Without an interpretation it is a practice lesson."""
    body = _json_body()
    session = coach.create_session(body.get("interpretation_id"), body.get("clinician_id"))
    return jsonify(session.to_dict()), 201


@api_bp.get("/coach/sessions")
def list_coach_sessions():
    """Training record, newest first. Filters: clinician_id, interpretation_id, limit."""
    query = CoachSession.query
    if request.args.get("clinician_id"):
        query = query.filter_by(clinician_id=request.args["clinician_id"])
    if request.args.get("interpretation_id"):
        query = query.filter_by(interpretation_id=_int(request.args["interpretation_id"], "interpretation_id"))
    limit = _int(request.args.get("limit"), "limit", 1, 200) or 50
    return jsonify([s.to_dict() for s in query.order_by(CoachSession.id.desc()).limit(limit)])


@api_bp.get("/coach/sessions/<int:session_id>")
def get_coach_session(session_id):
    session = _get_or_404(CoachSession, session_id)
    return jsonify(session.to_dict(include_transcript=request.args.get("transcript") in ("1", "true")))


@api_bp.post("/coach/sessions/<int:session_id>/token")
def coach_token(session_id):
    """Short-lived Anam session token for the coach, with this case in its prompt."""
    session = _get_or_404(CoachSession, session_id)
    try:
        token = coach.create_coach_token(current_app.config, session)
    except AvatarUnavailable as exc:
        current_app.logger.warning("Coach unavailable: %s", exc)
        return jsonify(error=str(exc)), 503
    return jsonify(token)


@api_bp.post("/coach/sessions/<int:session_id>/events")
def coach_event(session_id):
    """Record what happened in the lesson: {type, data}. See docs/API.md for the event types."""
    session = _get_or_404(CoachSession, session_id)
    body = _json_body()
    if body.get("anam_session_id"):
        session.anam_session_id = str(body["anam_session_id"])[:64]
    message = coach.apply_event(session, body.get("type"), body.get("data") or {})
    db.session.commit()
    return jsonify(message=message, session=session.to_dict())


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
