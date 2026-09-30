import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    JSON,
    Float,
    Enum as SQLEnum,
)
import enum
from app.core.database import Base


class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class CervicalAvatarReport(Base):
    """
    Represents a cervical screening report augmented with Anam AI Avatar narrative.
    """
    __tablename__ = "cervical_avatar_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(100), unique=True, nullable=False, index=True)
    patient_id = Column(String(100), nullable=False, index=True)
    clinician_id = Column(String(100), nullable=True, index=True)

    # Clinical findings & diagnosis
    screening_result = Column(String(150), nullable=False)
    confidence_score = Column(Float, nullable=True)
    findings_data = Column(JSON, nullable=True)
    recommendations = Column(Text, nullable=False)
    clinical_notes = Column(Text, nullable=True)

    # Anam Avatar generation & narrative text
    generated_script = Column(Text, nullable=False)
    anam_persona_id = Column(String(100), nullable=True)
    anam_session_token = Column(Text, nullable=True)
    anam_session_id = Column(String(100), nullable=True)
    anam_video_stream_url = Column(Text, nullable=True)
    anam_video_id = Column(String(100), nullable=True)
    anam_video_url = Column(Text, nullable=True)
    video_status = Column(String(50), default="pending", nullable=True)

    status = Column(
        String(20),
        default=ReportStatus.READY.value,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "patient_id": self.patient_id,
            "clinician_id": self.clinician_id,
            "screening_result": self.screening_result,
            "confidence_score": self.confidence_score,
            "findings_data": self.findings_data,
            "recommendations": self.recommendations,
            "clinical_notes": self.clinical_notes,
            "generated_script": self.generated_script,
            "anam_persona_id": self.anam_persona_id,
            "anam_session_token": self.anam_session_token,
            "anam_session_id": self.anam_session_id,
            "anam_video_stream_url": self.anam_video_stream_url,
            "anam_video_id": self.anam_video_id,
            "anam_video_url": self.anam_video_url,
            "video_status": self.video_status,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
