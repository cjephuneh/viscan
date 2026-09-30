"""Pre-screening intake: normalise what the patient told the avatar and turn it into visit context."""

import re
import secrets
from datetime import datetime, timezone

from ..models import SYMPTOMS, IntakeSession, db

CODE_ALPHABET = "ACDEFGHJKLMNPQRTUVWXY3479"

QUESTIONS = {
    "previous_screening": ("never", "negative", "positive", "unknown"),
    "previously_treated": "yes_no",
    "pregnant": "yes_no",
    "menstruating_now": "yes_no",
    "symptoms": "symptoms",
    "hiv_status": ("positive", "negative", "unknown", "prefer_not_to_say"),
    "parity": "number",
    "smoker": "yes_no",
    "contraception": "text",
    "phone": "phone",
    "result_channel": ("sms", "whatsapp", "none"),
    "consent": "yes_no",
}
SEXES = ("female", "male", "intersex", "prefer_not_to_say")
TOPICS = (
    "what_is_via", "why_screening_matters", "what_to_expect", "the_speculum", "the_vinegar_test",
    "how_long", "results_same_day", "if_positive_treatment", "privacy", "pain_and_comfort",
)
CONCERN_CATEGORIES = ("pain", "embarrassment", "results", "cancer_fear", "cost", "privacy", "partner", "other")
EVENT_TYPES = ("details", "answer", "feeling", "concern", "question", "topic", "breathing", "finish", "transcript")

_YES = {"yes", "y", "true", "1", "yeah", "yep", "i am", "i do"}
_NO = {"no", "n", "false", "0", "nope", "not", "i am not", "i don't", "never"}


class IntakeError(ValueError):
    pass


def new_code() -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        if not IntakeSession.query.filter_by(code=code).first():
            return code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value, limit=500) -> str:
    return str(value or "").strip()[:limit]


def _yes_no(value):
    word = _text(value).lower()
    if word in _YES:
        return True
    if word in _NO:
        return False
    return None


def _age(value):
    match = re.search(r"\d{1,3}", str(value or ""))
    age = int(match.group()) if match else None
    return age if age is not None and 8 <= age <= 110 else None


def normalise_answer(question: str, value):
    kind = QUESTIONS.get(question)
    if kind is None:
        raise IntakeError(f"Unknown question '{question}'.")
    if kind == "yes_no":
        return _yes_no(value)
    if kind == "number":
        match = re.search(r"\d{1,2}", str(value or ""))
        return int(match.group()) if match else None
    if kind == "symptoms":
        items = value if isinstance(value, list) else re.split(r"[,;]", str(value or ""))
        picked = [s.strip().lower() for s in items if s and s.strip().lower() in SYMPTOMS]
        if not picked:
            return []
        return sorted(set(picked) - {"none"}) or ["none"]
    if kind == "phone":
        phone = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
        return phone if len(phone.lstrip("+")) >= 7 else None
    if kind == "text":
        return _text(value, 120) or None
    word = _text(value).lower().replace(" ", "_")
    return word if word in kind else None


def apply_event(intake: IntakeSession, kind: str, data: dict) -> str:
    """Apply one avatar/tool event to the intake. Returns a short confirmation for the LLM."""
    if kind not in EVENT_TYPES:
        raise IntakeError(f"'type' must be one of {', '.join(EVENT_TYPES)}.")
    data = data or {}

    if kind == "details":
        if data.get("full_name"):
            intake.full_name = _text(data["full_name"], 120)
        if data.get("preferred_name"):
            intake.preferred_name = _text(data["preferred_name"], 60)
        if data.get("age") not in (None, ""):
            intake.age = _age(data["age"])
        if data.get("sex"):
            sex = _text(data["sex"]).lower().replace(" ", "_")
            intake.sex = sex if sex in SEXES else None
        if data.get("language"):
            intake.language = _text(data["language"], 32)
        return f"Saved details for {intake.preferred_name or intake.full_name or 'the patient'}."

    if kind == "answer":
        question = _text(data.get("question"))
        value = normalise_answer(question, data.get("value"))
        answers = dict(intake.answers or {})
        answers[question] = {"value": value, "said": _text(data.get("said") or data.get("value"), 300), "at": _now()}
        intake.answers = answers
        return f"Saved {question.replace('_', ' ')}."

    if kind == "feeling":
        try:
            level = max(1, min(5, int(data.get("level"))))
        except (TypeError, ValueError):
            raise IntakeError("'level' must be a number from 1 (calm) to 5 (very anxious).") from None
        intake.feelings = [*(intake.feelings or []), {"level": level, "note": _text(data.get("note"), 200), "at": _now()}]
        return f"Noted feeling level {level} of 5."

    if kind == "concern":
        category = _text(data.get("category")).lower()
        intake.concerns = [*(intake.concerns or []), {
            "concern": _text(data.get("concern"), 300),
            "category": category if category in CONCERN_CATEGORIES else "other",
            "at": _now(),
        }]
        return "Concern noted for the nurse."

    if kind == "question":
        intake.patient_questions = [*(intake.patient_questions or []), {
            "question": _text(data.get("question"), 300),
            "answered": bool(data.get("answered", True)),
            "at": _now(),
        }]
        return "Question noted."

    if kind == "topic":
        topic = _text(data.get("topic"))
        if topic not in TOPICS:
            raise IntakeError(f"Unknown topic '{topic}'.")
        if topic not in (intake.topics_covered or []):
            intake.topics_covered = [*(intake.topics_covered or []), topic]
        return f"Showing {topic.replace('_', ' ')}."

    if kind == "breathing":
        intake.breathing_exercises = (intake.breathing_exercises or 0) + 1
        return "Breathing exercise started on screen."

    if kind == "finish":
        intake.summary = _text(data.get("summary"), 2000) or intake.summary
        intake.status = "completed"
        intake.completed_at = datetime.now(timezone.utc)
        return f"Intake complete. The patient's check-in code is {intake.code}."

    messages = data.get("messages")
    if not isinstance(messages, list):
        raise IntakeError("'messages' must be a list.")
    intake.transcript = [
        {"role": _text(m.get("role"), 16), "content": _text(m.get("content"), 4000)}
        for m in messages[-400:] if isinstance(m, dict)
    ]
    return "Transcript saved."


def _answer(intake: IntakeSession, question: str):
    return ((intake.answers or {}).get(question) or {}).get("value")


def screening_prefill(intake: IntakeSession) -> dict:
    """Fields for the clinician's screening form, keyed like POST /interpret."""
    previous = _answer(intake, "previous_screening")
    hiv = _answer(intake, "hiv_status")
    return {
        "patient_external_id": f"INT-{intake.code}",
        "age": intake.age,
        "hiv_status": hiv if hiv in ("positive", "negative") else "unknown",
        "pregnant": _answer(intake, "pregnant"),
        "previously_treated": _answer(intake, "previously_treated"),
        "previous_screening_result": {"negative": "VIA_NEGATIVE", "positive": "VIA_POSITIVE"}.get(previous),
        "parity": _answer(intake, "parity"),
        "smoker": _answer(intake, "smoker"),
        "contraception": _answer(intake, "contraception"),
        "symptoms": [s for s in (_answer(intake, "symptoms") or []) if s != "none"],
        "phone": _answer(intake, "phone"),
        "result_channel": _answer(intake, "result_channel"),
    }


def nurse_flags(intake: IntakeSession) -> list[dict]:
    """Things the clinician should know before the exam, most important first."""
    flags = []

    def add(level, text):
        flags.append({"level": level, "text": text})

    if intake.sex and intake.sex not in ("female", "intersex"):
        add("alert", "Patient did not report being female: confirm VIA screening is appropriate.")
    if _answer(intake, "consent") is False:
        add("alert", "Patient has not agreed to the examination yet.")
    symptoms = [s for s in (_answer(intake, "symptoms") or []) if s != "none"]
    if symptoms:
        add("alert", "Reports " + ", ".join(s.replace("_", " ") for s in symptoms) + ".")
    if _answer(intake, "pregnant") is True:
        add("warn", "Pregnant: screening is possible but treatment is usually deferred.")
    elif _answer(intake, "pregnant") is None and "pregnant" in (intake.answers or {}):
        add("warn", "Unsure whether pregnant: consider a pregnancy test.")
    if _answer(intake, "menstruating_now") is True:
        add("warn", "Currently menstruating: VIA may be hard to read.")
    if _answer(intake, "hiv_status") == "positive":
        add("warn", "Living with HIV: higher risk, shorter screening interval.")
    if intake.age is not None and not 25 <= intake.age <= 65:
        add("info", f"Age {intake.age} is outside the usual 25-65 screening range.")
    anxiety = intake.anxiety()
    if anxiety["end"] is not None and anxiety["end"] >= 4:
        add("warn", f"Still anxious ({anxiety['end']}/5): take extra time and explain each step.")
    for concern in intake.concerns or []:
        add("info", f"Concern ({concern['category'].replace('_', ' ')}): {concern['concern']}")
    unanswered = [q["question"] for q in intake.patient_questions or [] if not q.get("answered")]
    if unanswered:
        add("info", "Questions for the nurse: " + "; ".join(unanswered))
    return flags


def intake_payload(intake: IntakeSession, include_transcript: bool = False) -> dict:
    data = intake.to_dict(include_transcript=include_transcript)
    data["prefill"] = screening_prefill(intake)
    data["flags"] = nurse_flags(intake)
    return data


def create_intake(language: str | None = None, channel: str = "avatar") -> IntakeSession:
    intake = IntakeSession(code=new_code(), language=_text(language, 32) or None,
                           channel=channel if channel in ("avatar", "form") else "avatar")
    db.session.add(intake)
    db.session.commit()
    return intake
