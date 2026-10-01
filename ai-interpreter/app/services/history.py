"""Past screenings: a searchable, paginated history of every AI reading and what happened next."""

from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_

from ..models import (
    SCREENING_VERDICTS, AIInterpretation, ClinicianAnnotation, CoachSession, IntakeSession, Notification,
    Patient, Referral, ScreeningVisit, ViaImage, db,
)
from .care import final_result

SORTS = ("newest", "oldest", "risk")
REVIEW_STATUSES = ("pending", "reviewed", "disputed")
SUSPICIOUS_RESULTS = ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER")


class HistoryError(ValueError):
    pass


def _date(value, field):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HistoryError(f"'{field}' must be a date (YYYY-MM-DD).") from None


def _int(value, field, default, lo, hi):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except ValueError:
        raise HistoryError(f"'{field}' must be an integer.") from None
    return max(lo, min(hi, number))


def _filtered(args):
    # Join only ViaImage/Patient (1:1 with the interpretation). Intake is filtered
    # via a subquery so we never need SELECT DISTINCT over JSON columns — Postgres
    # rejects that (`could not identify an equality operator for type json`).
    query = (AIInterpretation.query
             .join(ViaImage, AIInterpretation.image_id == ViaImage.id)
             .outerjoin(Patient, ViaImage.patient_id == Patient.id))

    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        intake_ids = (db.session.query(IntakeSession.interpretation_id)
                      .filter(or_(IntakeSession.full_name.ilike(like), IntakeSession.code.ilike(like))))
        conditions = [Patient.external_id.ilike(like), ViaImage.site.ilike(like),
                      AIInterpretation.id.in_(intake_ids)]
        if q.lstrip("#").isdigit():
            conditions.append(AIInterpretation.id == int(q.lstrip("#")))
        query = query.filter(or_(*conditions))

    verdict = args.get("verdict")
    if verdict:
        if verdict not in SCREENING_VERDICTS:
            raise HistoryError(f"'verdict' must be one of {', '.join(SCREENING_VERDICTS)}.")
        query = query.filter(AIInterpretation.screening_verdict == verdict)

    status = args.get("status")
    if status:
        if status not in REVIEW_STATUSES:
            raise HistoryError(f"'status' must be one of {', '.join(REVIEW_STATUSES)}.")
        query = query.filter(AIInterpretation.review_status == status)

    start, end = _date(args.get("from"), "from"), _date(args.get("to"), "to")
    if start:
        query = query.filter(AIInterpretation.created_at >= datetime.combine(start, time.min))
    if end:
        query = query.filter(AIInterpretation.created_at <= datetime.combine(end, time.max))

    if args.get("referred") in ("1", "true"):
        query = query.filter(AIInterpretation.id.in_(db.session.query(Referral.interpretation_id)))
    if args.get("overdue") in ("1", "true"):
        query = query.filter(AIInterpretation.follow_up_due < date.today())
    return query


def _row(interp: AIInterpretation, counts: dict) -> dict:
    image, patient = interp.image, interp.image.patient
    visit = db.session.get(ScreeningVisit, image.visit_id) if image.visit_id else None
    intake = IntakeSession.query.filter_by(interpretation_id=interp.id).first()
    final_via, source = final_result(interp)
    latest = max(interp.annotations, key=lambda a: a.created_at) if interp.annotations else None
    referral = (Referral.query.filter_by(interpretation_id=interp.id).order_by(Referral.id.desc()).first()
                if counts["referrals"].get(interp.id) else None)
    rec = interp.recommendation or {}
    base = "/api/v1"
    return {
        "interpretation_id": interp.id,
        "created_at": interp.created_at.isoformat() if interp.created_at else None,
        "patient_external_id": patient.external_id if patient else None,
        "patient_name": intake.full_name if intake else None,
        "intake_id": intake.id if intake else None,
        "age": visit.age_at_visit if visit and visit.age_at_visit is not None else (patient.age if patient else None),
        "hiv_status": visit.hiv_status if visit else None,
        "symptoms": (visit.symptoms or []) if visit else [],
        "site": image.site,
        "screening_verdict": interp.screening_verdict,
        "via_result": interp.via_result,
        "final_via_result": final_via,
        "final_is_suspicious": final_via in SUSPICIOUS_RESULTS,
        "result_source": source,
        "confirmed_by": latest.clinician_id if latest else None,
        "agrees_with_ai": latest.agrees_with_ai if latest else None,
        "clinician_notes": latest.notes if latest else None,
        "risk_score": interp.risk_score,
        "suspicion_level": interp.suspicion_level,
        "swede_score": interp.swede_score,
        "confidence": interp.confidence,
        "lesion_count": len(interp.lesions),
        "urgency": rec.get("urgency"),
        "action": rec.get("action"),
        "follow_up_due": interp.follow_up_due.isoformat() if interp.follow_up_due else None,
        "follow_up_overdue": bool(interp.follow_up_due and interp.follow_up_due < date.today()),
        "review_status": interp.review_status,
        "referral": {"hospital": referral.hospital.name if referral.hospital else None, "status": referral.status,
                     "urgency": referral.urgency} if referral else None,
        "notifications": counts["notifications"].get(interp.id, 0),
        "coach_sessions": counts["coach"].get(interp.id, 0),
        "links": {
            "self": f"{base}/interpretations/{interp.id}",
            "thumbnail": f"{base}/images/{image.id}/thumb.jpg",
            "image": f"{base}/images/{image.id}/file",
            "overlay": f"{base}/interpretations/{interp.id}/overlay.png",
            "report": f"{base}/interpretations/{interp.id}/report",
        },
    }


def _counts(model, ids):
    if not ids:
        return {}
    rows = (db.session.query(model.interpretation_id, func.count(model.id))
            .filter(model.interpretation_id.in_(ids)).group_by(model.interpretation_id).all())
    return dict(rows)


def summary() -> dict:
    total = AIInterpretation.query.count()
    by_verdict = dict(db.session.query(AIInterpretation.screening_verdict, func.count())
                      .group_by(AIInterpretation.screening_verdict).all())
    by_status = dict(db.session.query(AIInterpretation.review_status, func.count())
                     .group_by(AIInterpretation.review_status).all())
    reviewed = db.session.query(ClinicianAnnotation.agrees_with_ai).filter(
        ClinicianAnnotation.interpretation_id.isnot(None), ClinicianAnnotation.agrees_with_ai.isnot(None)).all()
    agree = sum(1 for (a,) in reviewed if a)
    return {
        "total": total,
        "suspicious": by_verdict.get("SUSPICIOUS", 0),
        "not_suspicious": by_verdict.get("NOT_SUSPICIOUS", 0),
        "indeterminate": by_verdict.get("INDETERMINATE", 0),
        "pending_review": by_status.get("pending", 0),
        "reviewed": by_status.get("reviewed", 0),
        "disputed": by_status.get("disputed", 0),
        "referred": db.session.query(func.count(func.distinct(Referral.interpretation_id))).scalar() or 0,
        "follow_up_overdue": AIInterpretation.query.filter(AIInterpretation.follow_up_due < date.today()).count(),
        "agreement_rate": round(agree / len(reviewed), 2) if reviewed else None,
        "last_screening_at": (lambda d: d.isoformat() if d else None)(
            db.session.query(func.max(AIInterpretation.created_at)).scalar()),
    }


def list_screenings(args) -> dict:
    sort = args.get("sort") or "newest"
    if sort not in SORTS:
        raise HistoryError(f"'sort' must be one of {', '.join(SORTS)}.")
    page = _int(args.get("page"), "page", 1, 1, 100000)
    per_page = _int(args.get("per_page"), "per_page", 20, 1, 100)

    query = _filtered(args)
    order = {
        "newest": [AIInterpretation.created_at.desc(), AIInterpretation.id.desc()],
        "oldest": [AIInterpretation.created_at.asc(), AIInterpretation.id.asc()],
        "risk": [AIInterpretation.risk_score.desc().nulls_last(), AIInterpretation.created_at.desc()],
    }[sort]
    total = query.count()
    items = query.order_by(*order).offset((page - 1) * per_page).limit(per_page).all()
    ids = [i.id for i in items]
    counts = {"referrals": _counts(Referral, ids), "notifications": _counts(Notification, ids),
              "coach": _counts(CoachSession, ids)}
    return {
        "items": [_row(i, counts) for i in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
        "summary": summary(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
