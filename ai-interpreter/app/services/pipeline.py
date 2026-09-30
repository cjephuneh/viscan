import hashlib
import io
import time
from datetime import date
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError

from ..models import AIInterpretation, ClinicianAnnotation, Lesion, Patient, ScreeningVisit, ViaImage, db
from .interpreter import ReferenceExample, build_interpreter, with_defaults
from .quality import assess_quality
from .rules import build_assessment, build_recommendation

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class PipelineError(ValueError):
    pass


def _load_image(image_bytes: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PipelineError("File is not a readable image.") from exc
    if img.format not in ALLOWED_FORMATS:
        raise PipelineError(f"Unsupported image format {img.format}; use JPEG, PNG or WEBP.")
    return img


def _prior_screens(patient: Patient | None) -> list[dict]:
    if patient is None or patient.id is None:
        return []
    rows = (
        AIInterpretation.query.join(ViaImage)
        .filter(ViaImage.patient_id == patient.id)
        .order_by(AIInterpretation.created_at.desc())
        .limit(10)
        .all()
    )
    prior = []
    for interp in rows:
        clinician = max(interp.annotations, key=lambda a: a.created_at) if interp.annotations else None
        prior.append({
            "interpretation_id": interp.id,
            "date": interp.created_at.date().isoformat() if interp.created_at else None,
            "via_result": clinician.via_result if clinician else interp.via_result,
            "source": "clinician" if clinician else "ai",
        })
    return prior


def _create_visit(patient: Patient | None, fields: dict) -> ScreeningVisit:
    visit = ScreeningVisit(
        patient=patient,
        visit_date=fields.get("visit_date") or date.today(),
        age_at_visit=fields.get("age") if fields.get("age") is not None else (patient.age if patient else None),
        hiv_status=fields.get("hiv_status") or (patient.hiv_status if patient else None),
        hpv_status=fields.get("hpv_status"),
        hpv_genotypes=fields.get("hpv_genotypes"),
        pregnant=fields.get("pregnant"),
        parity=fields.get("parity"),
        smoker=fields.get("smoker"),
        contraception=fields.get("contraception"),
        previously_treated=fields.get("previously_treated"),
        previous_screening_result=fields.get("previous_screening_result"),
        symptoms=fields.get("symptoms") or [],
        clinician_id=fields.get("clinician_id"),
        notes=fields.get("notes"),
    )
    db.session.add(visit)
    return visit


def _get_or_create_patient(fields: dict) -> Patient | None:
    external_id = (fields.get("patient_external_id") or "").strip()
    if not external_id:
        return None
    patient = Patient.query.filter_by(external_id=external_id).first()
    if patient is None:
        patient = Patient(external_id=external_id)
        db.session.add(patient)
    if fields.get("age") is not None:
        patient.age = fields["age"]
    if fields.get("hiv_status"):
        patient.hiv_status = fields["hiv_status"]
    return patient


def _reference_examples(limit: int, exclude_sha: str) -> list[ReferenceExample]:
    """Pick recent clinician-verified images, one per VIA class where possible."""
    if limit <= 0:
        return []
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    examples, seen_classes, seen_images = [], set(), set()
    candidates = (
        ClinicianAnnotation.query
        .filter(ClinicianAnnotation.via_result.in_(["VIA_NEGATIVE", "VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"]))
        .order_by(ClinicianAnnotation.created_at.desc())
        .limit(200)
        .all()
    )
    for ann in candidates:
        if len(examples) >= limit:
            break
        image = ann.image
        if ann.via_result in seen_classes or image.id in seen_images or image.sha256 == exclude_sha:
            continue
        path = upload_dir / image.filename
        if not path.exists():
            continue
        examples.append(ReferenceExample(image.id, path.read_bytes(), ann.via_result, ann.notes or ""))
        seen_classes.add(ann.via_result)
        seen_images.add(image.id)
    return examples


def analyze_image(image_bytes: bytes, fields: dict) -> dict:
    img = _load_image(image_bytes)
    sha = hashlib.sha256(image_bytes).hexdigest()
    ext = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[img.format]
    filename = f"{sha}.{ext}"
    path = Path(current_app.config["UPLOAD_DIR"]) / filename
    if not path.exists():
        path.write_bytes(image_bytes)

    quality = assess_quality(img)
    patient = _get_or_create_patient(fields)
    prior = _prior_screens(patient)
    visit = _create_visit(patient, fields)
    via_image = ViaImage(
        patient=patient,
        visit=visit,
        filename=filename,
        sha256=sha,
        mime_type=ALLOWED_FORMATS[img.format],
        width=img.width,
        height=img.height,
        site=fields.get("site"),
        device=fields.get("device"),
        quality=quality,
    )
    db.session.add(via_image)

    context = visit.context()
    if not context.get("previous_screening_result") and prior:
        context["previous_screening_result"] = prior[0]["via_result"]

    started = time.perf_counter()
    if not quality["acceptable"]:
        engine, model, examples = "quality_gate", "local", []
        ai = with_defaults({
            "image_modality": "unclear",
            "via_result": "INADEQUATE",
            "confidence": 1.0,
            "image_adequacy": {"adequate": False, "issues": quality["blocking_issues"]},
            "scj_visibility": "not_visible",
            "transformation_zone_type": "undetermined",
            "findings": {},
            "rationale": "Image failed the local quality gate; no AI interpretation attempted.",
        })
    else:
        interpreter = build_interpreter(current_app.config)
        engine, model = interpreter.engine, interpreter.model
        examples = _reference_examples(current_app.config["FEWSHOT_EXAMPLES"], sha) if engine == "openai" else []
        ai = with_defaults(interpreter.interpret(image_bytes, context, examples))
    latency_ms = int((time.perf_counter() - started) * 1000)

    recommendation = build_recommendation(ai, context, current_app.config["REVIEW_CONFIDENCE_THRESHOLD"])
    recommendation["flags"].extend(quality["warnings"])
    assessment = build_assessment(ai, context, recommendation, prior)

    interpretation = AIInterpretation(
        image=via_image,
        engine=engine,
        model=model,
        via_result=ai["via_result"],
        screening_verdict=assessment["screening_verdict"],
        suspicion_level=assessment["suspicion_level"],
        risk_score=assessment["risk_index"]["score"],
        swede_score=assessment["swede"]["total"],
        image_modality=ai.get("image_modality"),
        confidence=ai["confidence"],
        findings=ai,
        assessment=assessment,
        recommendation=recommendation,
        fewshot_image_ids=[e.image_id for e in examples],
        latency_ms=latency_ms,
        review_status="pending",
        follow_up_due=date.fromisoformat(assessment["follow_up_due"]) if assessment["follow_up_due"] else None,
    )
    for lesion in ai["lesions"]:
        interpretation.lesions.append(Lesion(**{k: lesion.get(k) for k in LESION_FIELDS}))
    db.session.add(interpretation)
    db.session.commit()
    return build_response(interpretation)


LESION_FIELDS = ("clock_start", "clock_end", "area_percent", "density", "margins", "surface",
                 "vessel_pattern", "touches_scj", "extends_into_canal", "bbox", "description")


def build_response(interp: AIInterpretation) -> dict:
    ai, assessment, rec = interp.findings, interp.assessment, interp.recommendation
    image, base = interp.image, "/api/v1"
    return {
        "interpretation_id": interp.id,
        "image_id": image.id,
        "patient_id": image.patient_id,
        "visit_id": image.visit_id,
        "created_at": interp.created_at.isoformat() if interp.created_at else None,
        "verdict": {
            "screening_verdict": assessment["screening_verdict"],
            "is_suspicious": assessment["is_suspicious"],
            "label": assessment["verdict_label"],
            "suspicion_level": assessment["suspicion_level"],
            "risk_score": assessment["risk_index"]["score"],
            "via_result": ai["via_result"],
            "confidence": ai["confidence"],
        },
        "diagnosis": {
            "via_result": ai["via_result"],
            "confidence": ai["confidence"],
            "summary": rec["action"],
            "urgency": rec["urgency"],
        },
        "clinical_summary": {
            "key_observations": ai.get("key_observations", []),
            "rationale": ai.get("rationale"),
            "patient_explanation": ai.get("patient_explanation"),
            "counselling_points": assessment["counselling_points"],
            "clinician_checklist": assessment["clinician_checklist"],
        },
        "image_assessment": {
            "image_modality": ai.get("image_modality"),
            "adequacy": ai.get("image_adequacy"),
            "model_quality_read": ai.get("image_quality"),
            "local_quality_metrics": image.quality,
            "scj_visibility": ai.get("scj_visibility"),
            "transformation_zone_type": ai.get("transformation_zone_type"),
        },
        "findings": ai.get("findings"),
        "lesions": [lesion.to_dict() for lesion in interp.lesions],
        "cancer_red_flags": ai.get("cancer_red_flags"),
        "benign_findings": ai.get("benign_findings"),
        "swede": assessment["swede"],
        "histology_likelihood": ai.get("histology_likelihood"),
        "differential": ai.get("differential"),
        "risk_index": assessment["risk_index"],
        "treatment_eligibility": assessment["treatment_eligibility"],
        "recommendation": rec,
        "follow_up_due": assessment["follow_up_due"],
        "history": assessment["history"],
        "visit": image.visit.to_dict() if image.visit else None,
        "review_status": interp.review_status,
        "engine": {"name": interp.engine, "model": interp.model, "latency_ms": interp.latency_ms,
                   "reference_examples": interp.fewshot_image_ids or []},
        "links": {
            "self": f"{base}/interpretations/{interp.id}",
            "image": f"{base}/images/{image.id}/file",
            "overlay": f"{base}/interpretations/{interp.id}/overlay.png",
            "report": f"{base}/interpretations/{interp.id}/report",
            "annotate": f"{base}/interpretations/{interp.id}/annotations",
        },
        "disclaimer": "Decision support only. A trained clinician must confirm every result before any treatment.",
    }
