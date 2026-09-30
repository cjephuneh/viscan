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
    # "acetic_acid" = the VIA frame that is interpreted (default);
    # "native" = optional pre-acetic-acid baseline of the same cervix.
    capture = db.Column(db.String(32), default="acetic_acid")
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
            "capture": self.capture or "acetic_acid",
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


class PartnerHospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(255))
    city = db.Column(db.String(80))
    phone = db.Column(db.String(40))
    whatsapp = db.Column(db.String(40))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    services = db.Column(db.JSON)
    opening_hours = db.Column(db.String(120))
    accepts_referrals = db.Column(db.Boolean, default=True)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self, distance_km: float | None = None):
        data = {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "phone": self.phone,
            "whatsapp": self.whatsapp,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "services": self.services or [],
            "opening_hours": self.opening_hours,
            "accepts_referrals": self.accepts_referrals,
            "is_demo": self.is_demo,
        }
        if distance_km is not None:
            data["distance_km"] = round(distance_km, 2)
        return data


class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    hospital_id = db.Column(db.Integer, db.ForeignKey("partner_hospital.id"), nullable=False)
    reason = db.Column(db.Text)
    urgency = db.Column(db.String(16))
    referred_by = db.Column(db.String(64))
    status = db.Column(db.String(24), default="sent")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    hospital = db.relationship("PartnerHospital")

    def to_dict(self):
        return {
            "id": self.id,
            "interpretation_id": self.interpretation_id,
            "patient_id": self.patient_id,
            "hospital": self.hospital.to_dict() if self.hospital else None,
            "reason": self.reason,
            "urgency": self.urgency,
            "referred_by": self.referred_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    channel = db.Column(db.String(16), nullable=False)
    recipient = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24), default="simulated")
    provider = db.Column(db.String(32), default="dummy")
    sent_by = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "interpretation_id": self.interpretation_id,
            "patient_id": self.patient_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "message": self.message,
            "status": self.status,
            "provider": self.provider,
            "sent_by": self.sent_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IntakeSession(db.Model):
    """Pre-screening conversation between the patient and the AI avatar."""

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), unique=True, index=True, nullable=False)
    status = db.Column(db.String(16), default="in_progress", index=True)
    channel = db.Column(db.String(16), default="avatar")
    anam_session_id = db.Column(db.String(64))
    full_name = db.Column(db.String(120))
    preferred_name = db.Column(db.String(60))
    age = db.Column(db.Integer)
    sex = db.Column(db.String(16))
    language = db.Column(db.String(32))
    answers = db.Column(db.JSON, default=dict)
    feelings = db.Column(db.JSON, default=list)
    concerns = db.Column(db.JSON, default=list)
    patient_questions = db.Column(db.JSON, default=list)
    topics_covered = db.Column(db.JSON, default=list)
    breathing_exercises = db.Column(db.Integer, default=0)
    summary = db.Column(db.Text)
    transcript = db.Column(db.JSON, default=list)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    visit_id = db.Column(db.Integer, db.ForeignKey("screening_visit.id"))
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True))

    def anxiety(self) -> dict:
        levels = [f["level"] for f in self.feelings or [] if isinstance(f.get("level"), int)]
        start, end = (levels[0], levels[-1]) if levels else (None, None)
        return {"start": start, "end": end, "change": (end - start) if len(levels) > 1 else None}

    def to_dict(self, include_transcript: bool = False):
        data = {
            "id": self.id,
            "code": self.code,
            "status": self.status,
            "channel": self.channel,
            "anam_session_id": self.anam_session_id,
            "full_name": self.full_name,
            "preferred_name": self.preferred_name,
            "age": self.age,
            "sex": self.sex,
            "language": self.language,
            "answers": self.answers or {},
            "feelings": self.feelings or [],
            "anxiety": self.anxiety(),
            "concerns": self.concerns or [],
            "patient_questions": self.patient_questions or [],
            "topics_covered": self.topics_covered or [],
            "breathing_exercises": self.breathing_exercises or 0,
            "summary": self.summary,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
            "interpretation_id": self.interpretation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_transcript:
            data["transcript"] = self.transcript or []
        return data


class CoachSession(db.Model):
    """A clinician's lesson with the AI coach, optionally about one interpretation."""

    id = db.Column(db.Integer, primary_key=True)
    interpretation_id = db.Column(db.Integer, db.ForeignKey("ai_interpretation.id"), index=True)
    clinician_id = db.Column(db.String(64), index=True)
    status = db.Column(db.String(16), default="active", index=True)
    anam_session_id = db.Column(db.String(64))
    topics = db.Column(db.JSON, default=list)
    quiz = db.Column(db.JSON, default=list)
    action_plan = db.Column(db.JSON, default=list)
    roleplays = db.Column(db.JSON, default=list)
    summary = db.Column(db.Text)
    transcript = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    ended_at = db.Column(db.DateTime(timezone=True))

    def score(self) -> dict:
        answered = [q for q in self.quiz or [] if q.get("chosen_index") is not None]
        return {"asked": len(self.quiz or []), "answered": len(answered),
                "correct": sum(1 for q in answered if q.get("correct"))}

    def to_dict(self, include_transcript: bool = False):
        data = {
            "id": self.id,
            "interpretation_id": self.interpretation_id,
            "clinician_id": self.clinician_id,
            "status": self.status,
            "topics": self.topics or [],
            "quiz": self.quiz or [],
            "score": self.score(),
            "action_plan": self.action_plan or [],
            "roleplays": self.roleplays or [],
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
        if include_transcript:
            data["transcript"] = self.transcript or []
        return data


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
