from sqlalchemy import Index, text

from app.extensions import db
from app.utils.time import utcnow

JOB_QUEUED = "queued"
JOB_PROCESSING = "processing"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"

ACTIVE_JOB_STATUSES = (JOB_QUEUED, JOB_PROCESSING)


class AnalysisJob(db.Model):
    """One VIA image waiting for, or finished with, the single analysis worker.

    Only one row may be ``processing`` at a time. That constraint is what keeps
    a second upload in the queue until the image already being analyzed finishes.
    """

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        Index("ix_analysis_jobs_status_queued_at", "status", "queued_at"),
        Index(
            "uq_analysis_jobs_one_processing",
            "status",
            unique=True,
            postgresql_where=text("status = 'processing'"),
            sqlite_where=text("status = 'processing'"),
        ),
        Index(
            "uq_analysis_jobs_one_active_image",
            "via_image_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
            sqlite_where=text("status IN ('queued', 'processing')"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    via_image_id = db.Column(
        db.Integer, db.ForeignKey("via_images.id"), nullable=False, index=True
    )
    screening_id = db.Column(
        db.Integer, db.ForeignKey("screenings.id"), nullable=False, index=True
    )
    status = db.Column(db.String(32), nullable=False, default=JOB_QUEUED)
    attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    error_detail = db.Column(db.Text, nullable=True)
    ai_result_id = db.Column(db.Integer, db.ForeignKey("ai_results.id"), nullable=True)
    queued_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)

    via_image = db.relationship("VIAImage", back_populates="analysis_jobs")
    screening = db.relationship("Screening", back_populates="analysis_jobs")
    ai_result = db.relationship("AIResult")
