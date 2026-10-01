from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ClinicalFindings(BaseModel):
    transformation_zone: Optional[str] = Field(
        None,
        description="Transformation Zone type (e.g., 'Type 1 - Fully visible', 'Type 2', 'Type 3')"
    )
    aceto_white_changes: Optional[str] = Field(
        None,
        description="Acetowhite lesion characteristics (e.g., 'Dense, opaque with distinct margins', 'Faint/translucent')"
    )
    lesion_quadrant: Optional[str] = Field(
        None,
        description="Clock-face location of any detected lesion (e.g., '12 to 3 o clock')"
    )
    vascular_patterns: Optional[str] = Field(
        None,
        description="Vascular pattern (e.g., 'Normal fine capillary network', 'Fine punctation', 'Coarse mosaic', 'Atypical vessels')"
    )
    lugol_iodine_reaction: Optional[str] = Field(
        None,
        description="Lugol iodine uptake (e.g., 'Schiller positive - Mustard yellow', 'Schiller negative - Mahogany brown')"
    )
    additional_observations: Optional[str] = Field(
        None,
        description="Any extra clinical observations from visual assessment"
    )


class ReportCreateRequest(BaseModel):
    scan_id: str = Field(..., description="Unique cervical scan or examination ID", example="SCAN-2026-0938")
    patient_id: str = Field(..., description="Anonymized Patient or Medical Record Number", example="PT-88319")
    clinician_id: Optional[str] = Field(None, description="Requesting clinician or reviewing physician ID", example="DR-MWIMULE-01")
    screening_result: str = Field(
        ...,
        description="Screening triage or AI assessment (e.g., 'High-grade Squamous Intraepithelial Lesion (HSIL)', 'Negative for Intraepithelial Lesion (NILM)')",
        example="High-grade Squamous Intraepithelial Lesion (HSIL)"
    )
    confidence_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="AI model confidence score (0.0 to 1.0)",
        example=0.94
    )
    findings: Optional[ClinicalFindings] = Field(
        None,
        description="Structured visual colposcopy / screening findings"
    )
    recommendations: str = Field(
        ...,
        description="Recommended clinical next steps or management plan",
        example="Immediate colposcopy with directed biopsy and HPV high-risk genotyping recommended."
    )
    clinical_notes: Optional[str] = Field(
        None,
        description="Supplemental physician or triage notes"
    )
    custom_script: Optional[str] = Field(
        None,
        description="Optional pre-generated narrative script. If omitted, the service builds a medical script automatically."
    )
    persona_id: Optional[str] = Field(
        None,
        description="Optional specific Anam Persona ID to present the report"
    )


class ReportResponse(BaseModel):
    id: str
    scan_id: str
    patient_id: str
    clinician_id: Optional[str]
    screening_result: str
    confidence_score: Optional[float]
    findings_data: Optional[Dict[str, Any]]
    recommendations: str
    clinical_notes: Optional[str]
    generated_script: str
    anam_persona_id: Optional[str]
    anam_session_token: Optional[str]
    anam_video_id: Optional[str] = None
    anam_video_url: Optional[str] = None
    video_status: Optional[str] = None
    player_url: Optional[str] = None
    status: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class VideoStatusResponse(BaseModel):
    report_id: str
    scan_id: str
    video_id: Optional[str]
    status: str = Field(..., description="Video rendering status: 'pending', 'running', 'completed', 'failed'")
    video_url: Optional[str] = Field(None, description="Direct playable MP4 video URL (usable in <video src=...>)")
    player_url: Optional[str] = Field(None, description="Ready-to-use HTML player page URL for iframes / previews")
    generated_script: Optional[str] = Field(
        None,
        description="Written narration script available immediately; MP4 may still be rendering.",
    )
    duration_seconds: Optional[float] = None
    expires_at: Optional[str] = None
    instructions: str = "Use video_url directly in HTML5 <video src=...> or player_url in an <iframe>."


class AnamSessionTokenRequest(BaseModel):
    persona_id: Optional[str] = Field(None, description="Optional custom persona ID override")


class AnamSessionTokenResponse(BaseModel):
    report_id: str
    session_token: str
    persona_id: Optional[str]
    system_prompt: str
    generated_script: str
    expires_in_seconds: int = 3600
    instructions: str = (
        "Pass this session_token to the Anam client SDK (e.g., @anam-ai/js-sdk createClient({ sessionToken })) "
        "to initiate WebRTC streaming to your video element."
    )


class HealthResponse(BaseModel):
    status: str
    service: str
    port: int
    environment: str
    database_connected: bool
    anam_configured: bool
    timestamp: datetime
