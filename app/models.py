from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

VIA_RESULTS = ("VIA_NEGATIVE", "VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER", "INADEQUATE")
HIV_STATUSES = ("positive", "negative", "unknown")
DIAGNOSIS_METHODS = ("colposcopy", "histology", "hpv_test", "cytology")
DIAGNOSIS_RESULTS = (
    "normal", "CIN1", "CIN2", "CIN3", "AIS", "invasive_cancer",
    "hpv_positive", "hpv_negative", "inconclusive",
)
CIN2_PLUS = ("CIN2", "CIN3", "AIS", "invasive_cancer")
TREATMENTS = (
    "none", "thermal_ablation", "cryotherapy", "LEEP",
    "cone_biopsy", "referred_oncology", "other",
)
SCREENING_VERDICTS = ("SUSPICIOUS", "NOT_SUSPICIOUS", "INDETERMINATE")
SYMPTOMS = (
    "postcoital_bleeding", "intermenstrual_bleeding", "postmenopausal_bleeding",
    "abnormal_discharge", "pelvic_pain", "dyspareunia", "none",
)
HPV_STATUSES = ("positive", "negative", "unknown")


def utcnow():
    return datetime.now(timezone.utc)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, index=True)
    age = db.Column(db.Integer)
    hiv_status = db.Column(db.String(16), default="unknown")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    images = db.relationship("ViaImage", backref="patient", lazy=True)
    visits = db.relationship("ScreeningVisit", backref="patient", lazy=True)
    diagnoses = db.relationship("DiagnosisRecord", backref="patient", lazy=True)
    outcomes = db.relationship("Outcome", backref="patient", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "external_id": self.external_id,
            "age": self.age,
            "hiv_status": self.hiv_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScreeningVisit(db.Model):
    """Clinical context captured at the time of screening."""

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=True)
    visit_date = db.Column(db.Date)
    age_at_visit = db.Column(db.Integer)
    hiv_status = db.Column(db.String(16))
    hpv_status = db.Column(db.String(16))
    hpv_genotypes = db.Column(db.String(64))
    pregnant = db.Column(db.Boolean)
    parity = db.Column(db.Integer)
    smoker = db.Column(db.Boolean)
    contraception = db.Column(db.String(64))
    previously_treated = db.Column(db.Boolean)
    previous_screening_result = db.Column(db.String(32))
    symptoms = db.Column(db.JSON)
    clinician_id = db.Column(db.String(64))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    images = db.relationship("ViaImage", backref="visit", lazy=True)

    def context(self) -> dict:
        return {
            "age": self.age_at_visit,
            "hiv_status": self.hiv_status,
            "hpv_status": self.hpv_status,
            "pregnant": self.pregnant,
            "previously_treated": self.previously_treated,
            "previous_screening_result": self.previous_screening_result,
            "symptoms": self.symptoms or [],
            "smoker": self.smoker,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "age_at_visit": self.age_at_visit,
            "hiv_status": self.hiv_status,
            "hpv_status": self.hpv_status,
            "hpv_genotypes": self.hpv_genotypes,
            "pregnant": self.pregnant,
            "parity": self.parity,
            "smoker": self.smoker,
            "contraception": self.contraception,
            "previously_treated": self.previously_treated,
            "previous_screening_result": self.previous_screening_result,
            "symptoms": self.symptoms or [],
            "clinician_id": self.clinician_id,
            "notes": self.notes,
        }


class ViaImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=True)
    visit_id = db.Column(db.Integer, db.ForeignKey("screening_visit.id"), nullable=True)
    filename = db.Column(db.String(128), nullable=False)
    sha256 = db.Column(db.String(64), index=True, nullable=False)
    mime_type = db.Column(db.String(32))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    site = db.Column(db.String(128))
    device = db.Column(db.String(128))
    quality = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    interpretations = db.relationship("AIInterpretation", backref="image", lazy=True)
    annotations = db.relationship("ClinicianAnnotation", backref="image", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
            "sha256": self.sha256,
            "width": self.width,
            "height": self.height,
            "site": self.site,
            "device": self.device,
            "quality": self.quality,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AIInterpretation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("via_image.id"), nullable=False)
    engine = db.Column(db.String(32))
    model = db.Column(db.String(64))
    via_result = db.Column(db.String(32), index=True)
    screening_verdict = db.Column(db.String(16), index=True)
    suspicion_level = db.Column(db.String(16))
    risk_score = db.Column(db.Integer, index=True)
    swede_score = db.Column(db.Integer)
    image_modality = db.Column(db.String(32))
    confidence = db.Column(db.Float)
    findings = db.Column(db.JSON)
    assessment = db.Column(db.JSON)
    recommendation = db.Column(db.JSON)
    fewshot_image_ids = db.Column(db.JSON)
    latency_ms = db.Column(db.Integer)
    review_status = db.Column(db.String(16), default="pending", index=True)
    follow_up_due = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    annotations = db.relationship("ClinicianAnnotation", backref="interpretation", lazy=True)
    lesions = db.relationship("Lesion", backref="interpretation", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "image_id": self.image_id,
            "engine": self.engine,
            "model": self.model,
            "via_result": self.via_result,
            "screening_verdict": self.screening_verdict,
            "suspicion_level": self.suspicion_level,
            "risk_score": self.risk_score,
            "swede_score": self.swede_score,
            "image_modality": self.image_modality,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "follow_up_due": self.follow_up_due.isoformat() if self.follow_up_due else None,
            "findings": self.findings,
            "assessment": self.assessment,
            "lesions": [lesion.to_dict() for lesion in self.lesions],
            "recommendation": self.recommendation,
            "fewshot_image_ids": self.fewshot_image_ids,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "annotations": [a.to_dict() for a in self.annotations],
        }


class Lesion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"), nullable=False)
    clock_start = db.Column(db.Integer)
    clock_end = db.Column(db.Integer)
    area_percent = db.Column(db.Integer)
    density = db.Column(db.String(16))
    margins = db.Column(db.String(24))
    surface = db.Column(db.String(16))
    vessel_pattern = db.Column(db.String(24))
    touches_scj = db.Column(db.Boolean)
    extends_into_canal = db.Column(db.Boolean)
    bbox = db.Column(db.JSON)
    description = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "clock_start": self.clock_start,
            "clock_end": self.clock_end,
            "area_percent": self.area_percent,
            "density": self.density,
            "margins": self.margins,
            "surface": self.surface,
            "vessel_pattern": self.vessel_pattern,
            "touches_scj": self.touches_scj,
            "extends_into_canal": self.extends_into_canal,
            "bbox": self.bbox,
            "description": self.description,
        }


class ClinicianAnnotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("via_image.id"), nullable=False)
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"))
    clinician_id = db.Column(db.String(64), nullable=False)
    via_result = db.Column(db.String(32), nullable=False)
    agrees_with_ai = db.Column(db.Boolean)
    lesion_clock_positions = db.Column(db.JSON)
    transformation_zone_type = db.Column(db.String(16))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "image_id": self.image_id,
            "interpretation_id": self.interpretation_id,
            "clinician_id": self.clinician_id,
            "via_result": self.via_result,
            "agrees_with_ai": self.agrees_with_ai,
            "lesion_clock_positions": self.lesion_clock_positions,
            "transformation_zone_type": self.transformation_zone_type,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DiagnosisRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey("via_image.id"))
    method = db.Column(db.String(32), nullable=False)
    result = db.Column(db.String(32), nullable=False)
    diagnosed_on = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "image_id": self.image_id,
            "method": self.method,
            "result": self.result,
            "diagnosed_on": self.diagnosed_on.isoformat() if self.diagnosed_on else None,
            "notes": self.notes,
        }


class Outcome(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey("via_image.id"))
    treatment = db.Column(db.String(32), default="none")
    treated_on = db.Column(db.Date)
    follow_up_on = db.Column(db.Date)
    follow_up_result = db.Column(db.String(32))
    status = db.Column(db.String(32), default="open")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "image_id": self.image_id,
            "treatment": self.treatment,
            "treated_on": self.treated_on.isoformat() if self.treated_on else None,
            "follow_up_on": self.follow_up_on.isoformat() if self.follow_up_on else None,
            "follow_up_result": self.follow_up_result,
            "status": self.status,
            "notes": self.notes,
        }
