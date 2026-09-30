from app.extensions import db
from app.utils.time import utcnow

SCREENING_STATUSES = (
    "CREATED",
    "IMAGE_UPLOADED",
    "QUEUED",
    "ANALYZING",
    "ANALYZED",
    "ANALYSIS_FAILED",
    "REVIEWED",
    "COMPLETED",
)


class Screening(db.Model):
    __tablename__ = "screenings"
    __table_args__ = (
        db.UniqueConstraint("patient_code", name="uq_screenings_patient_code"),
        db.Index("ix_screenings_facility_status", "facility_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facilities.id"), nullable=False)
    patient_code = db.Column(db.String(32), nullable=False)
    phone = db.Column(db.String(16), nullable=True)
    notify_channel = db.Column(db.String(16), nullable=True)
    screening_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="CREATED", server_default="CREATED")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    facility = db.relationship("Facility", back_populates="screenings")
    images = db.relationship(
        "VIAImage",
        back_populates="screening",
        order_by="VIAImage.uploaded_at",
    )
    analysis_jobs = db.relationship(
        "AnalysisJob",
        back_populates="screening",
        order_by="AnalysisJob.id",
    )
    assessment = db.relationship(
        "Assessment",
        back_populates="screening",
        uselist=False,
    )
