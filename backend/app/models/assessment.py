from app.extensions import db
from app.utils.time import utcnow


class Assessment(db.Model):
    """Clinician assessment. This is separate from the AI prediction."""

    __tablename__ = "assessments"

    id = db.Column(db.Integer, primary_key=True)
    screening_id = db.Column(
        db.Integer,
        db.ForeignKey("screenings.id"),
        nullable=False,
        unique=True,
    )
    result = db.Column(db.String(64), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    screening = db.relationship("Screening", back_populates="assessment")
