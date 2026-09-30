"""Deterministic clinical logic applied on top of the model's findings.

Based on WHO screen-and-treat guidance (2021): ablation (thermal or cryotherapy) is
appropriate only when the whole lesion and the squamocolumnar junction are visible, the
lesion covers < 75% of the ectocervix, does not extend into the canal, and there is no
suspicion of cancer. Otherwise refer for excision (LEEP) / colposcopy.
Intervals, weights and thresholds are programme parameters, not validated clinical truths."""

from datetime import date, timedelta

RESCREEN_MONTHS_NEGATIVE = 36
POST_TREATMENT_FOLLOW_UP_MONTHS = 12
INADEQUATE_RETAKE_MONTHS = 0
MAX_ABLATION_AREA_PERCENT = 75
BLEEDING_SYMPTOMS = {"postcoital_bleeding", "intermenstrual_bleeding", "postmenopausal_bleeding"}
MAJOR_RED_FLAGS = {"mass_or_exophytic_growth", "ulceration", "atypical_vessels", "necrosis", "irregular_contour"}


def _major_flags(ai: dict) -> list[str]:
    return [k for k, v in (ai.get("cancer_red_flags") or {}).items() if v and k in MAJOR_RED_FLAGS]

VERDICT_LABELS = {
    "SUSPICIOUS": "Suspicious - abnormal area seen, needs treatment or referral",
    "NOT_SUSPICIOUS": "Not suspicious - no lesion requiring treatment seen",
    "INDETERMINATE": "Indeterminate - image cannot be assessed, retake required",
}
RESULT_BASE_RISK = {"VIA_NEGATIVE": 5, "VIA_POSITIVE": 45, "SUSPICIOUS_FOR_CANCER": 80}


def screening_verdict(ai: dict, context: dict) -> str:
    result = ai["via_result"]
    if result == "INADEQUATE":
        return "INDETERMINATE"
    if result in ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"):
        return "SUSPICIOUS"
    return "NOT_SUSPICIOUS"


def risk_index(ai: dict, context: dict) -> dict:
    """Transparent additive screening-risk index (0-100) with an itemised breakdown."""
    result = ai["via_result"]
    if result == "INADEQUATE":
        return {"score": None, "level": "unknown", "breakdown": []}

    breakdown = [{"factor": f"AI result {result}", "points": RESULT_BASE_RISK[result]}]
    swede_total = sum(ai.get("swede", {}).values())
    if swede_total:
        breakdown.append({"factor": f"Swede features ({swede_total}/8)", "points": 2 * swede_total})
    flags = [k for k, v in (ai.get("cancer_red_flags") or {}).items() if v]
    if flags:
        breakdown.append({"factor": "Cancer red flags: " + ", ".join(f.replace("_", " ") for f in flags),
                          "points": min(15, 5 * len(flags))})
    probs = ai.get("histology_likelihood") or {}
    high_grade = probs.get("cin2_plus", 0) + probs.get("invasive_cancer", 0)
    if high_grade >= 0.3:
        breakdown.append({"factor": f"AI-estimated CIN2+ probability {high_grade:.0%}", "points": round(10 * high_grade)})
    if context.get("hiv_status") == "positive":
        breakdown.append({"factor": "Living with HIV", "points": 8})
    if context.get("hpv_status") == "positive":
        breakdown.append({"factor": "HPV positive", "points": 10})
    symptoms = set(context.get("symptoms") or []) & BLEEDING_SYMPTOMS
    if symptoms:
        breakdown.append({"factor": "Abnormal bleeding: " + ", ".join(s.replace("_", " ") for s in symptoms), "points": 6})
    if context.get("previously_treated"):
        breakdown.append({"factor": "Previously treated for precancer", "points": 5})
    if context.get("previous_screening_result") in ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"):
        breakdown.append({"factor": "Previous screen positive", "points": 5})
    if context.get("smoker"):
        breakdown.append({"factor": "Smoker", "points": 3})

    score = max(0, min(100, sum(item["points"] for item in breakdown)))
    level = "low" if score < 15 else "moderate" if score < 45 else "high" if score < 75 else "very_high"
    return {"score": score, "level": level, "breakdown": breakdown}


def swede_assessment(ai: dict) -> dict:
    parts = ai.get("swede") or {}
    total = sum(parts.values())
    if ai["via_result"] == "INADEQUATE":
        band = "not assessable"
    elif total <= 2:
        band = "low - consistent with normal or low-grade change"
    elif total <= 4:
        band = "intermediate - low-grade lesion likely; high grade not excluded"
    elif total <= 6:
        band = "elevated - possible high-grade lesion; histological confirmation advised"
    else:
        band = "high - features strongly suggest a high-grade lesion"
    return {
        "components": parts,
        "total": total,
        "max": 8,
        "interpretation": band,
        "note": "Modified Swede score without the iodine component (VIA only); bands are indicative.",
    }


def eligibility_checklist(ai: dict, context: dict) -> list[dict]:
    findings = ai.get("findings") or {}
    tz = ai.get("transformation_zone_type")
    area = int(findings.get("cervix_area_involved_percent") or 0)
    major = _major_flags(ai)

    def item(criterion, met, detail=""):
        return {"criterion": criterion, "met": met, "detail": detail}

    return [
        item("No suspicion of invasive cancer",
             ai["via_result"] != "SUSPICIOUS_FOR_CANCER" and not major,
             ", ".join(k.replace("_", " ") for k in major)),
        item("Squamocolumnar junction fully visible (TZ type 1 or 2)",
             None if tz == "undetermined" else tz in ("type_1", "type_2"), f"TZ {tz}"),
        item(f"Lesion covers < {MAX_ABLATION_AREA_PERCENT}% of the ectocervix",
             area < MAX_ABLATION_AREA_PERCENT, f"~{area}%"),
        item("Lesion does not extend into the endocervical canal",
             not findings.get("extends_into_canal"), ""),
        item("Not pregnant (otherwise defer treatment unless cancer suspected)",
             None if context.get("pregnant") is None else not context["pregnant"], ""),
    ]


def history_comparison(current_result: str, prior: list[dict]) -> dict:
    """prior: earlier screens for the same patient, newest first: {date, via_result}."""
    if not prior:
        return {"previous_screens": [], "trend": "first_screen_on_record", "days_since_last_screen": None}
    last = prior[0]
    positive = {"VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"}
    now_pos, was_pos = current_result in positive, last["via_result"] in positive
    if current_result == "INADEQUATE" or last["via_result"] == "INADEQUATE":
        trend = "not_comparable"
    elif now_pos and was_pos:
        trend = "persistent_positive"
    elif now_pos:
        trend = "new_positive"
    elif was_pos:
        trend = "resolved_since_last_screen"
    else:
        trend = "stable_negative"
    days = (date.today() - date.fromisoformat(last["date"])).days if last.get("date") else None
    return {"previous_screens": prior[:10], "trend": trend, "days_since_last_screen": days}


def counselling_points(verdict: str, recommendation: dict) -> list[str]:
    if verdict == "INDETERMINATE":
        return ["Explain that the picture was not clear enough and the check needs to be repeated today."]
    if verdict == "NOT_SUSPICIOUS":
        return [
            "Reassure: no area needing treatment was seen today.",
            f"Return for screening in {recommendation.get('follow_up_months') or RESCREEN_MONTHS_NEGATIVE} months, "
            "or sooner if abnormal bleeding or discharge develops.",
        ]
    points = [
        "Explain that an area of the cervix changed colour and needs attention; this is common and usually "
        "not cancer, and treating it early prevents cancer.",
    ]
    if recommendation.get("ablation_eligible"):
        points += [
            "Offer same-day ablation; describe mild cramping and watery discharge for up to 4 weeks.",
            "Advise no sexual intercourse or tampons for 4 weeks after treatment.",
            "Return urgently for fever, heavy bleeding, foul discharge or severe pain.",
        ]
    elif recommendation.get("urgency") == "urgent":
        points.append("Arrange the referral before the patient leaves; confirm contact details and transport.")
    else:
        points.append("Explain why referral is needed and confirm the appointment date.")
    points.append(f"Follow-up visit in {recommendation.get('follow_up_months')} months.")
    return points


def build_recommendation(ai: dict, patient_context: dict, review_threshold: float) -> dict:
    result = ai["via_result"]
    findings = ai.get("findings", {})
    confidence = float(ai.get("confidence", 0.0))
    reasons: list[str] = []
    flags: list[str] = []
    symptoms = set(patient_context.get("symptoms") or [])

    if confidence < review_threshold:
        flags.append(f"Low AI confidence ({confidence:.0%}); prioritise clinician review.")
    if patient_context.get("hiv_status") == "positive":
        flags.append("Woman living with HIV: higher risk of progression and recurrence.")
    if patient_context.get("hpv_status") == "positive":
        flags.append("HPV positive: VIA is being used for triage; a negative VIA does not exclude disease.")
    age = patient_context.get("age")
    if age is not None and (age < 25 or age > 65):
        flags.append(f"Age {age} is outside the typical 25-65 screening range; VIA accuracy may be reduced.")
    if age is not None and age >= 50:
        flags.append("Age 50+: the transformation zone often recedes into the canal, reducing VIA reliability.")
    if patient_context.get("pregnant"):
        flags.append("Pregnant: defer ablative treatment until after delivery unless cancer is suspected.")

    rec = {
        "category": result,
        "action": "",
        "urgency": "routine",
        "ablation_eligible": None,
        "follow_up_months": None,
        "reasons": reasons,
        "flags": flags,
        "requires_clinician_confirmation": True,
    }

    if result == "INADEQUATE":
        rec["action"] = "Retake the image (clean mucus/blood, reapply acetic acid, wait 1 minute, ensure the whole cervix and SCJ are in focus)."
        rec["follow_up_months"] = INADEQUATE_RETAKE_MONTHS
        reasons.extend(ai.get("image_adequacy", {}).get("issues", []))
        return rec

    if result == "VIA_NEGATIVE":
        if symptoms & BLEEDING_SYMPTOMS:
            rec["action"] = ("VIA negative, but the patient reports abnormal bleeding: refer for diagnostic "
                             "evaluation (symptomatic women should not be managed by screening alone).")
            rec["urgency"] = "soon"
            reasons.append("Symptomatic: " + ", ".join(sorted(s.replace("_", " ") for s in symptoms & BLEEDING_SYMPTOMS)))
        else:
            rec["action"] = "No acetowhite lesion requiring treatment. Rescreen per programme interval."
        rec["follow_up_months"] = RESCREEN_MONTHS_NEGATIVE
        return rec

    if result == "SUSPICIOUS_FOR_CANCER":
        rec["action"] = "Do NOT ablate. Urgent referral for biopsy and gynae-oncology evaluation."
        rec["urgency"] = "urgent"
        rec["ablation_eligible"] = False
        rec["follow_up_months"] = 1
        reasons.append("Features suspicious for invasive cancer.")
        return rec

    tz = ai.get("transformation_zone_type")
    area = int(findings.get("cervix_area_involved_percent") or 0)
    if tz == "type_3" or ai.get("scj_visibility") == "not_visible":
        reasons.append("Squamocolumnar junction / transformation zone not fully visible (type 3).")
    if tz == "undetermined":
        reasons.append("Transformation zone type could not be determined from the image.")
    if area >= MAX_ABLATION_AREA_PERCENT:
        reasons.append(f"Lesion covers ~{area}% of the ectocervix (limit {MAX_ABLATION_AREA_PERCENT}%).")
    if findings.get("extends_into_canal"):
        reasons.append("Lesion extends into the endocervical canal.")
    if findings.get("lesion_margins") == "raised_irregular":
        reasons.append("Raised/irregular margins warrant histological assessment.")
    if _major_flags(ai):
        reasons.append("Cancer red-flag features present; histology needed before any treatment.")
    if (ai.get("cancer_red_flags") or {}).get("contact_bleeding"):
        flags.append("Contact bleeding noted: confirm it is from ectropion/cervicitis and not the lesion before ablating.")
    if patient_context.get("pregnant"):
        reasons.append("Pregnancy: ablation deferred.")

    eligible = not reasons
    rec["ablation_eligible"] = eligible
    rec["follow_up_months"] = POST_TREATMENT_FOLLOW_UP_MONTHS
    rec["urgency"] = "soon"
    if eligible:
        rec["action"] = "VIA positive and eligible for ablation: offer same-visit thermal ablation or cryotherapy (screen-and-treat), with follow-up at 12 months."
    else:
        rec["action"] = "VIA positive but NOT eligible for ablation: refer for LEEP / colposcopy."
    return rec


def build_assessment(ai: dict, context: dict, recommendation: dict, prior: list[dict]) -> dict:
    verdict = screening_verdict(ai, context)
    risk = risk_index(ai, context)
    months = recommendation.get("follow_up_months")
    due = date.today() + timedelta(days=round(30.44 * months)) if months is not None else None
    checklist = eligibility_checklist(ai, context) if ai["via_result"] != "INADEQUATE" else []
    return {
        "screening_verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "is_suspicious": verdict == "SUSPICIOUS",
        "suspicion_level": risk["level"],
        "risk_index": risk,
        "swede": swede_assessment(ai),
        "treatment_eligibility": {
            "ablation_eligible": recommendation.get("ablation_eligible"),
            "checklist": checklist,
        },
        "follow_up_due": due.isoformat() if due else None,
        "history": history_comparison(ai["via_result"], prior),
        "counselling_points": counselling_points(verdict, recommendation),
        "clinician_checklist": [
            "Confirm the AI result by direct visual inspection before acting.",
            "Check the whole transformation zone, including the canal, with the speculum repositioned if needed.",
            *ai.get("recommended_checks", []),
            "Record your own VIA result in VIScan (agree/disagree) to improve the model.",
        ],
    }
