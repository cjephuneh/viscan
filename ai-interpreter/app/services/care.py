"""Post-screening care: supplies, referral need, patient messages and demo partner hospitals."""

from ..models import AIInterpretation, PartnerHospital, db

DEMO_PARTNERS = [
    # Illustrative placeholders around the default location; replace via POST /partner-hospitals.
    ("VIScan Partner Referral Hospital (demo)", 0.012, 0.006, ["colposcopy", "LEEP", "biopsy", "gynae-oncology"], "24 hours"),
    ("Women's Health Centre (demo)", -0.018, 0.021, ["colposcopy", "LEEP", "thermal ablation"], "Mon-Sat 08:00-18:00"),
    ("District Hospital Screening Unit (demo)", 0.031, -0.024, ["VIA screening", "thermal ablation", "cryotherapy"], "Mon-Fri 08:00-17:00"),
    ("Regional Cancer Care Centre (demo)", -0.045, -0.038, ["gynae-oncology", "biopsy", "radiotherapy referral"], "Mon-Fri 08:00-16:00"),
]


def seed_demo_partners(lat: float, lng: float) -> None:
    if PartnerHospital.query.first() is not None:
        return
    for i, (name, dlat, dlng, services, hours) in enumerate(DEMO_PARTNERS, start=1):
        db.session.add(PartnerHospital(
            name=name,
            address="Demo address - replace with a real partner",
            city="Demo",
            phone=f"+000 000 000 00{i}",
            whatsapp=f"+000 000 000 00{i}",
            latitude=lat + dlat,
            longitude=lng + dlng,
            services=services,
            opening_hours=hours,
            accepts_referrals=True,
            is_demo=True,
        ))
    db.session.commit()


def final_result(interp: AIInterpretation) -> tuple[str, str]:
    """(via_result, source): the latest clinician read overrides the AI."""
    if interp.annotations:
        latest = max(interp.annotations, key=lambda a: a.created_at)
        return latest.via_result, "clinician"
    return interp.via_result, "ai"


def suggested_supplies(via_result: str, recommendation: dict, findings: dict) -> list[dict]:
    """Items a pharmacy visit may cover. Medicines only on a clinician's prescription."""
    if via_result not in ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"):
        return []
    items = [
        {"item": "Pain relief (e.g. paracetamol or ibuprofen)", "why": "Cramping after treatment or biopsy",
         "prescription": False},
        {"item": "Sanitary pads", "why": "Watery discharge or light bleeding for up to 4 weeks after treatment",
         "prescription": False},
    ]
    if "cervicitis" in (findings.get("benign_findings") or []):
        items.append({"item": "Treatment for cervicitis per national syndromic guidelines",
                      "why": "Cervicitis noted on the image", "prescription": True})
    if recommendation.get("urgency") == "urgent":
        items.append({"item": "No purchase needed before referral",
                      "why": "Suspected cancer: go to the referral hospital first", "prescription": False})
    return items


def compose_message(interp: AIInterpretation, channel: str, hospital: PartnerHospital | None) -> str:
    via_result, _ = final_result(interp)
    patient = interp.image.patient
    ref = f" Ref: {patient.external_id}." if patient and patient.external_id else ""
    due = interp.follow_up_due.strftime("%d %b %Y") if interp.follow_up_due else None
    greeting = "Hello, this is your clinic (VIScan)."

    if via_result == "SUSPICIOUS_FOR_CANCER":
        body = "Your cervical screening needs an urgent specialist check."
    elif via_result == "VIA_POSITIVE":
        body = "Your cervical screening found an area that needs treatment or a closer check. This is common and treatable."
    elif via_result == "INADEQUATE":
        body = "Your cervical screening picture was not clear. Please come back so we can repeat it."
    else:
        body = "Your cervical screening did not show any area needing treatment."

    if hospital and via_result in ("VIA_POSITIVE", "SUSPICIOUS_FOR_CANCER"):
        contact = f" ({hospital.phone})" if hospital.phone else ""
        body += f" You have been referred to {hospital.name}{contact}."
    if due and via_result != "INADEQUATE":
        body += f" Next visit by {due}."
    closing = " Reply or call the clinic with any questions." if channel == "whatsapp" else ""
    return f"{greeting} {body}{ref}{closing}"
