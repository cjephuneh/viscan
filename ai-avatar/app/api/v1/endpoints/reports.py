import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import AsyncSessionLocal, get_db
from app.models.avatar_report import CervicalAvatarReport, ReportStatus
from app.schemas.avatar_report import (
    ReportCreateRequest,
    ReportResponse,
    AnamSessionTokenRequest,
    AnamSessionTokenResponse,
    VideoStatusResponse,
)
from app.services.clinical_formatter import ClinicalFormatter
from app.services.anam_service import anam_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_player_url(report_id: str) -> str:
    return f"/player/{report_id}"


async def _start_video_render_background(report_id: str) -> None:
    """Kick off Anam MP4 rendering after the written report is already saved.

    Keeps create-report fast so the clinician can read the script / Present live
    without waiting ~1 minute for the recording job to start.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CervicalAvatarReport).where(CervicalAvatarReport.id == report_id)
            )
            report = result.scalar_one_or_none()
            if report is None or report.anam_video_id:
                return
            video_job = await anam_service.create_avatar_video(script=report.generated_script)
            report.anam_video_id = video_job.get("id")
            report.video_status = video_job.get("status", "running")
            content = video_job.get("content", {})
            if content.get("available") and content.get("url"):
                report.anam_video_url = content.get("url")
                report.video_status = "completed"
            await db.commit()
            logger.info("Background video render started for report %s (%s)", report_id, report.anam_video_id)
    except Exception as exc:
        logger.warning("Background video render failed for report %s: %s", report_id, exc)


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Cervical Avatar Report",
    description=(
        "Ingest cervical scan findings, format the clinician avatar script immediately, "
        "and return the written report. MP4 rendering continues in the background."
    ),
)
async def create_cervical_report(
    payload: ReportCreateRequest,
    background_tasks: BackgroundTasks,
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

    # 1. Generate narration script locally (fast) and save the written report.
    #    Live Present uses POST /session later; MP4 render starts in the background.
    script = ClinicalFormatter.generate_narration_script(payload)
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
        anam_session_token=None,
        anam_video_id=None,
        anam_video_url=None,
        video_status="pending",
        status=ReportStatus.READY.value,
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)

    background_tasks.add_task(_start_video_render_background, report.id)

    resp = ReportResponse.model_validate(report)
    resp.player_url = _build_player_url(report.id)
    return resp


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
    out = []
    for r in reports:
        item = ReportResponse.model_validate(r)
        item.player_url = _build_player_url(r.id)
        out.append(item)
    return out


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

    # Check if video was pending/running and now completed
    if report.anam_video_id and (not report.anam_video_url or report.video_status != "completed"):
        try:
            video_info = await anam_service.get_avatar_video(report.anam_video_id)
            report.video_status = video_info.get("status", report.video_status)
            content = video_info.get("content", {})
            if content.get("available") and content.get("url"):
                report.anam_video_url = content.get("url")
                report.video_status = "completed"
            await db.commit()
            await db.refresh(report)
        except Exception as e:
            logger.debug(f"Video status polling error: {e}")

    resp = ReportResponse.model_validate(report)
    resp.player_url = _build_player_url(report.id)
    return resp


@router.post(
    "/{report_id}/video",
    response_model=VideoStatusResponse,
    summary="Trigger Video Render for Report",
    description="Requests an MP4 avatar video render from Anam AI for this report script.",
)
async def trigger_report_video(
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

    try:
        video_job = await anam_service.create_avatar_video(script=report.generated_script)
        report.anam_video_id = video_job.get("id")
        report.video_status = video_job.get("status", "running")
        content = video_job.get("content", {})
        if content.get("available") and content.get("url"):
            report.anam_video_url = content.get("url")
            report.video_status = "completed"

        await db.commit()
        await db.refresh(report)

        return VideoStatusResponse(
            report_id=report.id,
            scan_id=report.scan_id,
            video_id=report.anam_video_id,
            status=report.video_status,
            video_url=report.anam_video_url,
            player_url=_build_player_url(report.id),
            generated_script=report.generated_script,
            duration_seconds=video_job.get("durationSeconds"),
            expires_at=content.get("expiresAt"),
        )
    except Exception as e:
        logger.error(f"Failed to trigger video render: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Anam video render error: {e}",
        )


@router.get(
    "/{report_id}/video",
    response_model=VideoStatusResponse,
    summary="Get Video URL & Status",
    description="Check the rendering status of the MP4 video and retrieve the direct playable URL once ready.",
)
async def get_report_video_url(
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

    if not report.anam_video_id:
        # Trigger video generation on the fly if not already initiated
        try:
            video_job = await anam_service.create_avatar_video(script=report.generated_script)
            report.anam_video_id = video_job.get("id")
            report.video_status = video_job.get("status", "running")
            await db.commit()
            await db.refresh(report)
        except Exception as e:
            logger.error(f"Failed to initiate video on demand: {e}")
            return VideoStatusResponse(
                report_id=report.id,
                scan_id=report.scan_id,
                video_id=None,
                status="uninitiated",
                video_url=None,
                player_url=_build_player_url(report.id),
                generated_script=report.generated_script,
            )

    # Check status from Anam if not already completed
    duration = None
    expires_at = None
    if report.anam_video_id:
        try:
            info = await anam_service.get_avatar_video(report.anam_video_id)
            report.video_status = info.get("status", report.video_status)
            duration = info.get("durationSeconds")
            content = info.get("content", {})
            if content.get("available") and content.get("url"):
                report.anam_video_url = content.get("url")
                report.video_status = "completed"
                expires_at = content.get("expiresAt")
            await db.commit()
            await db.refresh(report)
        except Exception as e:
            logger.warning(f"Failed to query video status from Anam: {e}")

    return VideoStatusResponse(
        report_id=report.id,
        scan_id=report.scan_id,
        video_id=report.anam_video_id,
        status=report.video_status or "pending",
        video_url=report.anam_video_url,
        player_url=_build_player_url(report.id),
        generated_script=report.generated_script,
        duration_seconds=duration,
        expires_at=expires_at,
    )


@router.post(
    "/{report_id}/session",
    response_model=AnamSessionTokenResponse,
    summary="Generate Fresh Anam WebRTC Session Token",
    description="Generates an active, short-lived session token for real-time interactive avatar streaming.",
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
