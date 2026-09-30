import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.models.avatar_report import CervicalAvatarReport, ReportStatus
from app.schemas.avatar_report import (
    ReportCreateRequest,
    ReportResponse,
    AnamSessionTokenRequest,
    AnamSessionTokenResponse,
)
from app.services.clinical_formatter import ClinicalFormatter
from app.services.anam_service import anam_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Cervical Avatar Report",
    description="Ingest cervical scan findings from upstream Viscan backend, format clinician avatar script, and initialize Anam session.",
)
async def create_cervical_report(
    payload: ReportCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    # Check if scan_id already exists
    query = select(CervicalAvatarReport).where(CervicalAvatarReport.scan_id == payload.scan_id)
    result = await db.execute(query)
    existing_report = result.scalar_one_or_none()
    if existing_report:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A report for scan_id '{payload.scan_id}' already exists (ID: {existing_report.id}).",
        )

    # 1. Generate narration script from clinical findings
    script = ClinicalFormatter.generate_narration_script(payload)

    # 2. Build system prompt for Anam AI Persona
    system_prompt = ClinicalFormatter.build_anam_system_prompt(payload, script)

    # 3. Request initial Anam Session Token
    session_token = None
    try:
        session_data = await anam_service.create_session_token(
            system_prompt=system_prompt,
            persona_id=payload.persona_id,
        )
        session_token = session_data.get("sessionToken")
    except Exception as e:
        logger.warning(f"Could not initialize immediate Anam session token: {e}")

    # 4. Save to PostgreSQL database
    findings_dict = payload.findings.model_dump() if payload.findings else None

    report = CervicalAvatarReport(
        scan_id=payload.scan_id,
        patient_id=payload.patient_id,
        clinician_id=payload.clinician_id,
        screening_result=payload.screening_result,
        confidence_score=payload.confidence_score,
        findings_data=findings_dict,
        recommendations=payload.recommendations,
        clinical_notes=payload.clinical_notes,
        generated_script=script,
        anam_persona_id=payload.persona_id,
        anam_session_token=session_token,
        status=ReportStatus.READY.value,
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)

    return report


@router.get(
    "",
    response_model=List[ReportResponse],
    summary="List Cervical Reports",
    description="Retrieve reports with optional filtering by patient_id or scan_id.",
)
async def list_reports(
    patient_id: Optional[str] = Query(None, description="Filter by Patient ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(CervicalAvatarReport)
    if patient_id:
        query = query.where(CervicalAvatarReport.patient_id == patient_id)

    query = query.order_by(CervicalAvatarReport.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    reports = result.scalars().all()
    return reports


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get Report By ID or Scan ID",
)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    query = select(CervicalAvatarReport).where(
        or_(
            CervicalAvatarReport.id == report_id,
            CervicalAvatarReport.scan_id == report_id,
        )
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )
    return report


@router.post(
    "/{report_id}/session",
    response_model=AnamSessionTokenResponse,
    summary="Generate Fresh Anam WebRTC Session Token",
    description="Generates an active, short-lived session token for the clinician frontend to stream the digital avatar in real time.",
)
async def generate_avatar_session(
    report_id: str,
    payload: Optional[AnamSessionTokenRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(CervicalAvatarReport).where(
        or_(
            CervicalAvatarReport.id == report_id,
            CervicalAvatarReport.scan_id == report_id,
        )
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )

    # Reconstruct Clinical Findings if present
    findings_model = None
    if report.findings_data:
        findings_model = ClinicalFormatter.build_anam_system_prompt

    # Build prompt and request token
    dummy_req = ReportCreateRequest(
        scan_id=report.scan_id,
        patient_id=report.patient_id,
        screening_result=report.screening_result,
        confidence_score=report.confidence_score,
        recommendations=report.recommendations,
        clinical_notes=report.clinical_notes,
    )
    system_prompt = ClinicalFormatter.build_anam_system_prompt(dummy_req, report.generated_script)

    target_persona_id = (
        payload.persona_id if payload and payload.persona_id else report.anam_persona_id
    )

    try:
        session_data = await anam_service.create_session_token(
            system_prompt=system_prompt,
            persona_id=target_persona_id,
        )
        token = session_data.get("sessionToken", "")
    except Exception as e:
        logger.error(f"Failed to create Anam session token: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anam AI session generation failed: {e}",
        )

    # Update latest session token in DB
    report.anam_session_token = token
    await db.commit()

    return AnamSessionTokenResponse(
        report_id=report.id,
        session_token=token,
        persona_id=target_persona_id,
        system_prompt=system_prompt,
        generated_script=report.generated_script,
        expires_in_seconds=3600,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Report",
)
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    query = select(CervicalAvatarReport).where(
        or_(
            CervicalAvatarReport.id == report_id,
            CervicalAvatarReport.scan_id == report_id,
        )
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )

    await db.delete(report)
    await db.commit()
    return None
