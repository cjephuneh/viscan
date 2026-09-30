"""Durable FIFO queue for VIA analysis.

Uploads return as soon as the image and its job are stored. A single worker
claims the oldest queued job, calls the AI service, then claims the next one.
The database allows only one ``processing`` row, so a second API process cannot
analyze two images at the same time.
"""

from __future__ import annotations

from datetime import timezone

from flask import current_app
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app.errors import APIError
from app.extensions import db
from app.models.ai_result import AIResult
from app.models.analysis_job import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_PROCESSING,
    JOB_QUEUED,
    ACTIVE_JOB_STATUSES,
    AnalysisJob,
)
from app.models.screening import Screening
from app.models.via_image import VIAImage
from app.utils.time import utcnow

_FROZEN_SCREENING_STATUSES = ("REVIEWED", "COMPLETED")
_RECENTLY_FINISHED_LIMIT = 20


def enqueue_image(image: VIAImage) -> AnalysisJob:
    """Put an image on the queue. An image already queued or processing is not added twice."""
    if image.id is None:
        db.session.flush()

    existing = active_job_for_image(image.id)
    if existing is not None:
        _wake_worker()
        return existing

    job = AnalysisJob(
        screening_id=image.screening_id,
        status=JOB_QUEUED,
        attempts=0,
        queued_at=utcnow(),
    )
    image.analysis_jobs.append(job)
    db.session.flush()
    sync_screening_status(image.screening)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = active_job_for_image(image.id)
        if existing is not None:
            _wake_worker()
            return existing
        raise
    _wake_worker()
    return job


def active_job_for_image(image_id: int) -> AnalysisJob | None:
    return (
        AnalysisJob.query.filter(
            AnalysisJob.via_image_id == image_id,
            AnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(AnalysisJob.id.desc())
        .first()
    )


def process_next() -> bool:
    """Claim and finish one job. False means the queue had nothing this worker could take."""
    recover_stale_jobs()
    claimed = claim_next()
    if claimed is None:
        return False

    job_id, image_id, attempt = claimed
    db.session.remove()
    try:
        payload = _analyze(image_id)
    except APIError as exc:
        _finish_job(job_id, attempt, error_detail=exc.detail)
        return True
    except Exception:
        current_app.logger.exception("analysis job %s failed", job_id)
        db.session.remove()
        _finish_job(job_id, attempt, error_detail="Analysis failed unexpectedly.")
        return True

    _finish_job(job_id, attempt, payload=payload)
    return True


def build_queue_view() -> dict:
    active = (
        AnalysisJob.query.filter(AnalysisJob.status.in_(ACTIVE_JOB_STATUSES))
        .order_by(AnalysisJob.queued_at.asc(), AnalysisJob.id.asc())
        .all()
    )
    processing_job = next((job for job in active if job.status == JOB_PROCESSING), None)
    queued_jobs = [job for job in active if job.status == JOB_QUEUED]
    finished = (
        AnalysisJob.query.filter(AnalysisJob.status.in_((JOB_COMPLETED, JOB_FAILED)))
        .order_by(AnalysisJob.finished_at.desc(), AnalysisJob.id.desc())
        .limit(_RECENTLY_FINISHED_LIMIT)
        .all()
    )

    queued_payloads = []
    for index, job in enumerate(queued_jobs):
        ahead = index + (1 if processing_job is not None else 0)
        queued_payloads.append(present_job(job, (ahead + 1, ahead)))

    return {
        "processing_count": 1 if processing_job is not None else 0,
        "queued_count": len(queued_jobs),
        "processing": present_job(processing_job, (1, 0)) if processing_job is not None else None,
        "queued": queued_payloads,
        "recently_finished": [present_job(job, (None, None)) for job in finished],
    }


def present_job(job: AnalysisJob, rank: tuple[int | None, int | None] | None = None) -> dict:
    if rank is None:
        rank = rank_job(job)
    position, ahead = rank
    return {
        "id": job.id,
        "via_image_id": job.via_image_id,
        "screening_id": job.screening_id,
        "status": job.status,
        "position": position,
        "ahead": ahead,
        "attempts": job.attempts,
        "error_detail": job.error_detail,
        "ai_result_id": job.ai_result_id,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "ai_result": job.ai_result,
    }


def rank_job(job: AnalysisJob) -> tuple[int | None, int | None]:
    if job.status == JOB_PROCESSING:
        return 1, 0
    if job.status != JOB_QUEUED:
        return None, None

    processing = (
        db.session.query(AnalysisJob.id).filter(AnalysisJob.status == JOB_PROCESSING).count()
    )
    earlier = (
        db.session.query(AnalysisJob.id)
        .filter(
            AnalysisJob.status == JOB_QUEUED,
            or_(
                AnalysisJob.queued_at < job.queued_at,
                and_(
                    AnalysisJob.queued_at == job.queued_at,
                    AnalysisJob.id < job.id,
                ),
            ),
        )
        .count()
    )
    ahead = processing + earlier
    return ahead + 1, ahead


def sync_screening_status(screening: Screening) -> None:
    if screening.status in _FROZEN_SCREENING_STATUSES:
        return

    jobs = (
        AnalysisJob.query.filter_by(screening_id=screening.id)
        .order_by(AnalysisJob.id.asc())
        .all()
    )
    if any(job.status == JOB_PROCESSING for job in jobs):
        screening.status = "ANALYZING"
    elif any(job.status == JOB_QUEUED for job in jobs):
        screening.status = "QUEUED"
    elif jobs and jobs[-1].status == JOB_COMPLETED:
        screening.status = "ANALYZED"
    elif jobs and jobs[-1].status == JOB_FAILED:
        screening.status = "ANALYSIS_FAILED"
    screening.updated_at = utcnow()


def recover_stale_jobs() -> None:
    """Return a processing job to the queue if its worker died before finishing it."""
    stale_after = _stale_after_seconds()
    max_attempts = int(current_app.config["QUEUE_MAX_ATTEMPTS"])
    now = utcnow()
    jobs = AnalysisJob.query.filter_by(status=JOB_PROCESSING).all()
    changed = False
    for job in jobs:
        if _age_seconds(job.started_at, now) < stale_after:
            continue
        changed = True
        if job.attempts >= max_attempts:
            job.status = JOB_FAILED
            job.error_detail = "Analysis did not finish and was removed from the queue."
            job.finished_at = now
        else:
            job.status = JOB_QUEUED
            job.started_at = None
        db.session.flush()
        sync_screening_status(job.screening)
    if changed:
        db.session.commit()


def claim_next() -> tuple[int, int, int] | None:
    busy = (
        db.session.query(AnalysisJob.id).filter(AnalysisJob.status == JOB_PROCESSING).first()
    )
    if busy is not None:
        return None

    job = (
        AnalysisJob.query.filter_by(status=JOB_QUEUED)
        .order_by(AnalysisJob.queued_at.asc(), AnalysisJob.id.asc())
        .first()
    )
    if job is None:
        return None

    attempt = int(job.attempts or 0) + 1
    job_id = job.id
    image_id = job.via_image_id
    screening_id = job.screening_id
    rows = (
        db.session.query(AnalysisJob)
        .filter(AnalysisJob.id == job_id, AnalysisJob.status == JOB_QUEUED)
        .update(
            {
                "status": JOB_PROCESSING,
                "started_at": utcnow(),
                "attempts": AnalysisJob.attempts + 1,
            },
            synchronize_session=False,
        )
    )
    if rows != 1:
        db.session.rollback()
        return None

    db.session.expire(job)
    screening = db.session.get(Screening, screening_id)
    if screening is not None and screening.status not in _FROZEN_SCREENING_STATUSES:
        screening.status = "ANALYZING"
        screening.updated_at = utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None

    current_app.logger.info("analysis job %s processing image %s", job_id, image_id)
    return job_id, image_id, attempt


def _analyze(image_id: int) -> dict:
    from app.services.ai_service import analyze_image

    public_base = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
    image_url = f"{public_base}/api/v1/images/{image_id}/file"
    return analyze_image(image_url=image_url, image_id=image_id)


def _finish_job(
    job_id: int,
    attempt: int,
    *,
    payload: dict | None = None,
    error_detail: str | None = None,
) -> None:
    job = db.session.get(AnalysisJob, job_id)
    if job is None or job.status != JOB_PROCESSING or job.attempts != attempt:
        current_app.logger.warning(
            "skipping finish for analysis job %s attempt %s", job_id, attempt
        )
        db.session.rollback()
        return

    if payload is None:
        job.status = JOB_FAILED
        job.error_detail = (error_detail or "Analysis failed.")[:500]
    else:
        result = AIResult(
            via_image_id=job.via_image_id,
            prediction=payload["prediction"],
            confidence=payload["confidence"],
            model_version=payload["model_version"],
            processing_time_ms=payload["processing_time_ms"],
        )
        db.session.add(result)
        db.session.flush()
        job.ai_result_id = result.id
        job.status = JOB_COMPLETED
        job.error_detail = None

    job.finished_at = utcnow()
    db.session.flush()
    sync_screening_status(job.screening)
    db.session.commit()
    current_app.logger.info("analysis job %s %s", job.id, job.status)


def _wake_worker() -> None:
    from app.services.analysis_worker import wake_analysis_worker

    wake_analysis_worker()


def _stale_after_seconds() -> float:
    configured = float(current_app.config["QUEUE_STALE_SECONDS"])
    timeout = float(current_app.config["AI_TIMEOUT_SECONDS"])
    return max(configured, timeout + 15)


def _age_seconds(started_at, now) -> float:
    if started_at is None:
        return _stale_after_seconds()
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return (now - started_at).total_seconds()
