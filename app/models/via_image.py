from app.extensions import db
from app.utils.time import utcnow


class VIAImage(db.Model):
    __tablename__ = "via_images"

    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(db.Integer, db.ForeignKey("screenings.id"), nullable=False, index=True)
    file_path = db.Column(db.String(512), nullable=False, unique=True)
    media_type = db.Column(db.String(64), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    screening = db.relationship("Screening", back_populates="images")
    ai_results = db.relationship(
        "AIResult",
        back_populates="via_image",
        order_by="AIResult.created_at",
    )
