"""Six presentation clients. Typing the ID on a new screening fills the visit from these rows."""

from ..models import Patient, ScreeningVisit, db

DEMO_CLIENTS = (
    {
        "external_id": "0012",
        "age": 29,
        "hiv_status": "negative",
        "hpv_status": "negative",
        "pregnant": False,
        "previously_treated": False,
        "smoker": False,
        "parity": 1,
        "symptoms": [],
        "site": "Remera Health Centre",
    },
    {
        "external_id": "0013",
        "age": 38,
        "hiv_status": "positive",
        "hpv_status": "positive",
        "pregnant": False,
        "previously_treated": True,
        "smoker": False,
        "parity": 3,
        "symptoms": ["postcoital_bleeding"],
        "site": "Muhima Health Centre",
    },
    {
        "external_id": "0014",
        "age": 24,
        "hiv_status": "negative",
        "hpv_status": "unknown",
        "pregnant": True,
        "previously_treated": False,
        "smoker": False,
        "parity": 0,
        "symptoms": [],
        "site": "Kimironko Health Centre",
    },
    {
        "external_id": "0015",
        "age": 54,
        "hiv_status": "negative",
        "hpv_status": "negative",
        "pregnant": False,
        "previously_treated": False,
        "smoker": True,
        "parity": 6,
        "symptoms": ["postmenopausal_bleeding"],
        "site": "Nyamirambo Health Centre",
    },
    {
        "external_id": "0016",
        "age": 33,
        "hiv_status": "unknown",
        "hpv_status": "positive",
        "pregnant": False,
        "previously_treated": False,
        "smoker": False,
        "parity": 2,
        "symptoms": ["abnormal_discharge"],
        "site": "Kicukiro Health Centre",
    },
    {
        "external_id": "0017",
        "age": 46,
        "hiv_status": "positive",
        "hpv_status": "negative",
        "pregnant": False,
        "previously_treated": True,
        "smoker": True,
        "parity": 4,
        "symptoms": ["pelvic_pain", "dyspareunia"],
        "site": "Gikondo Health Centre",
    },
)


def seed_demo_clients() -> None:
    """Insert any missing demo clients. Safe to run on every start."""
    added = False
    for row in DEMO_CLIENTS:
        patient = Patient.query.filter_by(external_id=row["external_id"]).first()
        if patient is None:
            patient = Patient(
                external_id=row["external_id"],
                age=row["age"],
                hiv_status=row["hiv_status"],
            )
            db.session.add(patient)
            db.session.flush()
            added = True
        if ScreeningVisit.query.filter_by(patient_id=patient.id).first() is None:
            db.session.add(ScreeningVisit(
                patient_id=patient.id,
                age_at_visit=row["age"],
                hiv_status=row["hiv_status"],
                hpv_status=row["hpv_status"],
                pregnant=row["pregnant"],
                previously_treated=row["previously_treated"],
                smoker=row["smoker"],
                parity=row["parity"],
                symptoms=row["symptoms"],
                site=row["site"],
            ))
            added = True
    if added:
        db.session.commit()
