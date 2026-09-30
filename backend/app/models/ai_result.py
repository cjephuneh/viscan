from app.extensions import db
from app.utils.time import utcnow


class AIResult(db.Model):
    """Stored AI output. Rows are kept so later model versions can be compared."""

    __tablename__ = "ai_results"

    id = db.Column(db.Integer, primary_key=True)
    via_image_id = db.Column(db.Integer, db.ForeignKey("via_images.id"), nullable=False, index=True)
    prediction = db.Column(db.String(64), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    model_version = db.Column(db.String(64), nullable=False)
    processing_time_ms = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    via_image = db.relationship("VIAImage", back_populates="ai_results")
