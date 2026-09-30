from collections import Counter

from ..models import CIN2_PLUS, VIA_RESULTS, AIInterpretation, DiagnosisRecord

SCREEN_POSITIVE = {"VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"}
REFERENCE_METHODS = ("histology", "colposcopy")


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    ai_counts = Counter(a for a, _ in pairs)
    cl_counts = Counter(b for _, b in pairs)
    expected = sum(ai_counts[c] * cl_counts[c] for c in VIA_RESULTS) / (n * n)
    return round((observed - expected) / (1 - expected), 3) if expected < 1 else 1.0


def _reference_diagnosis(interp: AIInterpretation) -> DiagnosisRecord | None:
    image = interp.image
    query = DiagnosisRecord.query.filter(DiagnosisRecord.method.in_(REFERENCE_METHODS))
    linked = query.filter_by(image_id=image.id).order_by(DiagnosisRecord.created_at.desc()).first()
    if linked or image.patient_id is None:
        return linked
    return (
        query.filter_by(patient_id=image.patient_id, image_id=None)
        .order_by(DiagnosisRecord.created_at.desc())
        .first()
    )


def compute_metrics() -> dict:
    interpretations = AIInterpretation.query.filter(AIInterpretation.engine != "quality_gate").all()

    pairs, confusion = [], {a: Counter() for a in VIA_RESULTS}
    tp = fp = tn = fn = 0
    by_engine = Counter()

    for interp in interpretations:
        by_engine[interp.engine] += 1
        if interp.annotations:
            clinician = max(interp.annotations, key=lambda a: a.created_at).via_result
            pairs.append((interp.via_result, clinician))
            confusion[interp.via_result][clinician] += 1

        ref = _reference_diagnosis(interp)
        if ref is None or interp.via_result == "INADEQUATE":
            continue
        disease = ref.result in CIN2_PLUS
        positive = interp.via_result in SCREEN_POSITIVE
        if positive and disease:
            tp += 1
        elif positive:
            fp += 1
        elif disease:
            fn += 1
        else:
            tn += 1

    all_interps = AIInterpretation.query.all()
    agreement = sum(a == b for a, b in pairs)
    return {
        "total_interpretations": len(interpretations),
        "by_engine": dict(by_engine),
        "by_verdict": dict(Counter(i.screening_verdict for i in all_interps if i.screening_verdict)),
        "by_via_result": dict(Counter(i.via_result for i in all_interps)),
        "by_review_status": dict(Counter(i.review_status for i in all_interps if i.review_status)),
        "average_risk_score": (
            round(sum(scores) / len(scores), 1)
            if (scores := [i.risk_score for i in all_interps if i.risk_score is not None]) else None
        ),
        "clinician_agreement": {
            "reviewed": len(pairs),
            "agreement_rate": _ratio(agreement, len(pairs)),
            "cohens_kappa": _cohens_kappa(pairs),
            "confusion_matrix_ai_vs_clinician": {a: dict(c) for a, c in confusion.items() if c},
        },
        "vs_histology_cin2_plus": {
            "cases_with_reference": tp + fp + tn + fn,
            "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn,
            "sensitivity": _ratio(tp, tp + fn),
            "specificity": _ratio(tn, tn + fp),
            "ppv": _ratio(tp, tp + fp),
            "npv": _ratio(tn, tn + fn),
        },
    }
