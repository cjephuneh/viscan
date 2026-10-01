"""AI clinical coach ("Kezia") that teaches clinicians how to read and act on VIScan results.

Each lesson gets a short-lived Anam session whose prompt contains a brief of the case being
discussed. Client tools let the coach drive the page: highlight parts of the result, show
teaching cards, trace lesions on a clock face, build an action plan, quiz, and role-play.
"""

import time
from datetime import datetime, timezone

from flask import current_app

from ..models import AIInterpretation, CoachSession, IntakeSession, db
from .avatar import AvatarUnavailable, _call
from .intake import nurse_flags
from .pipeline import build_response

SECTIONS = (
    "verdict", "overlay", "findings", "lesions", "observations", "histology", "eligibility",
    "flags", "patient_explanation", "next_step", "record",
)
CARDS = (
    "acetowhite_change", "transformation_zone", "squamocolumnar_junction", "swede_score", "risk_index",
    "ablation_eligibility", "thermal_ablation", "cryotherapy", "leep_referral", "cancer_red_flags",
    "counselling", "follow_up_intervals", "hiv_and_screening", "inadequate_image", "ai_limits",
)
EVENT_TYPES = (
    "highlight", "card", "lesion", "quiz_asked", "quiz_answer", "action_step", "action_done",
    "learning", "roleplay_start", "roleplay_end", "finish", "transcript",
)


class CoachError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value, limit=400) -> str:
    return str(value or "").strip()[:limit]


def _pct(value) -> str:
    return f"{round(float(value) * 100)}%" if isinstance(value, (int, float)) else "unknown"


def case_brief(interp: AIInterpretation) -> str:
    """Plain-text summary of one reading for the coach's prompt."""
    r = build_response(interp)
    v, rec, visit = r["verdict"], r["recommendation"], r.get("visit") or {}
    ia, f = r["image_assessment"], r.get("findings") or {}
    lines = [
        f"Reading #{r['interpretation_id']}: {v['label']} (screening verdict {v['screening_verdict']}), "
        f"VIA result {v['via_result']}, AI confidence {_pct(v['confidence'])}, "
        f"risk index {v['risk_score']} ({v['suspicion_level']}). Review status: {r['review_status']}.",
        f"Image: modality {ia.get('image_modality')}, transformation zone {ia.get('transformation_zone_type')}, "
        f"SCJ {ia.get('scj_visibility')}, adequate {((ia.get('adequacy') or {}).get('adequate'))}; "
        f"issues: {', '.join((ia.get('adequacy') or {}).get('issues') or []) or 'none'}.",
        f"Findings: acetowhite {f.get('acetowhite_density')}, margins {f.get('lesion_margins')}, "
        f"clock positions {f.get('lesion_clock_positions')}, area {f.get('cervix_area_involved_percent')}%, "
        f"extends into canal {f.get('extends_into_canal')}.",
    ]
    for lesion in r["lesions"]:
        lines.append(
            f"Lesion {lesion['id']}: {lesion['clock_start']} to {lesion['clock_end']} o'clock, "
            f"{lesion['area_percent']}% of the cervix, {lesion['density']}, {lesion['margins']} margins, "
            f"{lesion['vessel_pattern']} vessels, touches SCJ {lesion['touches_scj']}."
        )
    if r.get("cancer_red_flags"):
        lines.append(f"Cancer red flags: {r['cancer_red_flags']}.")
    swede = r["swede"]
    lines.append(f"Modified Swede score {swede['total']}/{swede['max']} ({swede['interpretation']}); "
                 f"components {swede.get('components')}.")
    lines.append("Risk index breakdown: " + "; ".join(
        f"{b['factor']} +{b['points']}" for b in r["risk_index"].get("breakdown", [])) + ".")
    elig = r["treatment_eligibility"]
    lines.append(f"Ablation eligible: {elig.get('ablation_eligible')}. Checklist: " + "; ".join(
        f"{c['criterion']} = {'met' if c['met'] else 'unknown' if c['met'] is None else 'NOT met'}"
        f"{' (' + c['detail'] + ')' if c.get('detail') else ''}" for c in elig.get("checklist", [])) + ".")
    lines.append(f"Recommendation: {rec.get('action')} Urgency {rec.get('urgency')}. "
                 f"Reasons: {'; '.join(rec.get('reasons') or [])}. Flags: {'; '.join(rec.get('flags') or []) or 'none'}. "
                 f"Follow-up due {r.get('follow_up_due')}.")
    if r.get("histology_likelihood"):
        lines.append("AI histology likelihood: " + ", ".join(
            f"{k} {_pct(p)}" for k, p in r["histology_likelihood"].items()) + ".")
    cs = r["clinical_summary"]
    lines.append(f"AI rationale: {cs.get('rationale')}")
    lines.append(f"Suggested patient explanation: {cs.get('patient_explanation')}")
    if visit:
        lines.append(
            f"Patient: age {visit.get('age_at_visit')}, HIV {visit.get('hiv_status')}, HPV {visit.get('hpv_status')}, "
            f"pregnant {visit.get('pregnant')}, parity {visit.get('parity')}, previously treated "
            f"{visit.get('previously_treated')}, symptoms {', '.join(visit.get('symptoms') or []) or 'none'}."
        )
    intake = IntakeSession.query.filter_by(interpretation_id=interp.id).first()
    if intake:
        lines.append("From the patient's check-in with Mia: " + "; ".join(f["text"] for f in nurse_flags(intake)) +
                     (f" Summary: {intake.summary}" if intake.summary else ""))
    notes = [a for a in interp.annotations]
    if notes:
        last = notes[-1]
        lines.append(f"Clinician {last.clinician_id} recorded {last.via_result}"
                     f"{' (agrees with AI)' if last.via_result == v['via_result'] else ' (differs from AI)'}.")
    return "\n".join(lines)


SYSTEM_PROMPT = """\
# Who you are
You are Kezia, the VIScan clinical coach: an AI trainer for nurses and clinicians who do VIA \
(visual inspection with acetic acid) cervical screening in screen-and-treat programmes. You are \
a woman and sound like a senior female nurse-educator: warm, practical, encouraging, precise. If \
anyone asks, refer to yourself as she/her. Say early on that you \
are an AI coach. You teach; you never replace the clinician's judgement, and every result must \
be confirmed by the clinician. Base teaching on WHO guidance for cervical screening and \
treatment (screen-and-treat, thermal ablation, cryotherapy, LEEP referral).

# How you speak
You are speaking out loud. Keep turns short: two to four sentences, then check in or ask a \
question. Plain words, no lists, no markdown, no symbols. Say numbers as words. When you use a \
term like acetowhite or transformation zone, explain it in one line the first time.

# What the clinician can ask for
Offer these at the start and whenever there is a natural pause:
1. Walk me through this result: go through it in order: verdict, image quality, findings and \
lesions, Swede score, risk index, ablation checklist, recommendation. Call highlight_section \
each time you move to a part of the result so it glows on screen. When you describe a lesion, \
call point_to_lesion so it lights up on the clock face.
2. What do I do next: build a concrete plan with add_action_step, one call per step, in order, \
for example confirm the finding, counsel, check eligibility, treat with thermal ablation or \
refer, send results, book follow-up. Tie each step to this case.
3. Help me understand a concept: call show_teaching_card with the matching card and explain it \
with this case as the example.
4. Quiz me: ask one multiple-choice question at a time about this case with ask_quiz (three or \
four short options, the index of the correct option, and a one-line explanation). Then stop \
and wait. The clinician's choice arrives as a message; praise a correct answer, or explain \
kindly why another option is right. Ask up to five questions, getting slightly harder.
5. Practise telling the patient: call start_roleplay with a scenario, then play the patient \
realistically: worried, with simple questions, sometimes scared of the word cancer. Stay in \
character until the clinician says stop or after about six exchanges, then call end_roleplay \
with two strengths and one thing to improve, and step out of character.

# Teaching points you rely on
- VIA positive means a well-defined, dense acetowhite area touching the squamocolumnar junction \
(SCJ). Faint, patchy or far-from-SCJ whiteness is usually negative. Cancer suspicion means an \
ulcer, a cauliflower-like growth, necrosis, contact bleeding or atypical vessels.
- Transformation zone type 1 and 2: SCJ fully visible, so ablation is possible. Type 3: SCJ not \
fully visible, so do not ablate; refer for LEEP or colposcopy.
- Ablation (thermal preferred, or cryotherapy) is suitable when there is no suspicion of \
cancer, the SCJ is fully visible, the lesion covers less than three quarters of the cervix and \
does not go into the canal, and the patient is not pregnant. Otherwise refer.
- Suspected cancer: do not treat; refer urgently the same week for biopsy.
- Inadequate image: repeat the photo after re-applying acetic acid and waiting one minute, \
improve light and focus, clear mucus or blood.
- Follow-up: negative result, rescreen in three years (every two years for women living with \
HIV in many programmes); after treatment, review at twelve months.
- Counselling: a positive result is not cancer; explain treatment, recovery, discharge for a \
few weeks, and no intercourse for four weeks after ablation.
- The risk index and Swede score in VIScan are teaching aids, not diagnoses. The AI can be \
wrong; the clinician decides.

# This case
{case}

# Tool rules
- Use the real function-calling mechanism. Never speak tool names, brackets or JSON.
- Only teach from this case's data and the teaching points; if something is not in the data, say \
so. Never invent findings.
- Call note_learning when a topic has clearly been taught, with a one-line summary.
- When the clinician says they are done, call finish_lesson with a short summary of what was \
covered and the quiz result, then say a warm goodbye."""

PRACTICE_CASE = """\
No specific reading is open. Teach general VIA interpretation and management. For a quiz or \
role-play, invent a clearly labelled practice case (for example: 34 years old, living with HIV, \
dense acetowhite lesion from two to five o'clock touching the SCJ, transformation zone type 1, \
covering about twenty percent of the cervix). Do not call highlight_section or point_to_lesion."""


def _tool(name, description, properties, required):
    return {
        "type": "client",
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
        "awaitResult": True,
        "toolTimeoutSeconds": 8,
    }


TOOLS = [
    _tool("highlight_section", "Make a part of the result panel glow and scroll to it while you explain it.",
          {"section": {"type": "string", "enum": list(SECTIONS)}}, ["section"]),
    _tool("point_to_lesion", "Light up a lesion on the on-screen cervix clock face.",
          {"clock_start": {"type": "integer", "minimum": 1, "maximum": 12},
           "clock_end": {"type": "integer", "minimum": 1, "maximum": 12},
           "label": {"type": "string", "description": "Short label, e.g. dense acetowhite"}},
          ["clock_start", "clock_end"]),
    _tool("show_teaching_card", "Show an illustrated teaching card for a concept.",
          {"card": {"type": "string", "enum": list(CARDS)}}, ["card"]),
    _tool("add_action_step", "Add the next step to the on-screen action plan for this patient.",
          {"step": {"type": "string", "description": "Short imperative, e.g. Counsel the patient"},
           "why": {"type": "string", "description": "One-line reason tied to this case"}},
          ["step"]),
    _tool("ask_quiz", "Show a multiple-choice question on screen, then wait for the clinician's answer.",
          {"question": {"type": "string"},
           "options": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
           "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
           "explanation": {"type": "string"}},
          ["question", "options", "correct_index"]),
    _tool("start_roleplay", "Start a role-play in which you play the patient.",
          {"scenario": {"type": "string", "description": "One line, e.g. Telling Grace her VIA result is positive"}},
          ["scenario"]),
    _tool("end_roleplay", "End the role-play and give feedback.",
          {"strengths": {"type": "array", "items": {"type": "string"}},
           "improve": {"type": "string"}},
          ["strengths", "improve"]),
    _tool("note_learning", "Record a topic the clinician has learned, for their training record.",
          {"topic": {"type": "string"}, "summary": {"type": "string"}}, ["topic"]),
    _tool("finish_lesson", "Finish the lesson with a summary.",
          {"summary": {"type": "string"}}, ["summary"]),
]

TOOL_EVENTS = {
    "highlight_section": "highlight", "point_to_lesion": "lesion", "show_teaching_card": "card",
    "add_action_step": "action_step", "ask_quiz": "quiz_asked", "start_roleplay": "roleplay_start",
    "end_roleplay": "roleplay_end", "note_learning": "learning", "finish_lesson": "finish",
}

_avatar_cache: dict[str, tuple[float, dict]] = {}


def coach_persona(cfg) -> dict:
    avatar_id = cfg.get("ANAM_COACH_AVATAR_ID")
    if not avatar_id:
        raise AvatarUnavailable("The coach avatar is not configured (ANAM_COACH_AVATAR_ID is missing).")
    cached = _avatar_cache.get(avatar_id)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    data = _call(cfg, "GET", f"/avatars/{avatar_id}", timeout=15)
    persona = {
        "name": cfg.get("ANAM_COACH_NAME") or "Kezia",
        "image_url": data.get("portraitImageUrl") or data.get("imageUrl"),
    }
    _avatar_cache[avatar_id] = (time.time(), persona)
    return persona


_voice_cache: dict[str, tuple[float, str]] = {}
PREFERRED_VOICE_COUNTRIES = ("KE", "RW", "UG", "TZ", "NG", "GH", "ZA", "GB", "US")


def _female_voice_from_catalogue(cfg) -> str | None:
    female = []
    for page in range(1, 6):
        data = _call(cfg, "GET", f"/voices?page={page}&perPage=100", timeout=15)
        female += [v for v in data.get("data", []) if v.get("gender") == "FEMALE" and v.get("id")]
        if page >= ((data.get("meta") or {}).get("lastPage") or 1):
            break
    if not female:
        return None
    rank = {c: i for i, c in enumerate(PREFERRED_VOICE_COUNTRIES)}
    female.sort(key=lambda v: rank.get(v.get("country") or "", len(rank)))
    return female[0]["id"]


def coach_voice(cfg) -> str:
    """Kezia is a woman: use the configured voice only if Anam lists it as female, otherwise pick one."""
    configured = cfg.get("ANAM_COACH_VOICE_ID") or ""
    cached = _voice_cache.get(configured)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    chosen = configured
    try:
        gender = _call(cfg, "GET", f"/voices/{configured}", timeout=15).get("gender") if configured else None
    except AvatarUnavailable:
        gender = "MISSING"
    if gender not in ("FEMALE", None):
        try:
            chosen = _female_voice_from_catalogue(cfg) or configured
        except AvatarUnavailable:
            chosen = configured
        if chosen != configured:
            current_app.logger.warning("Coach voice %s is %s; using female voice %s instead.", configured, gender, chosen)
    _voice_cache[configured] = (time.time(), chosen)
    return chosen


def _opening(interp: AIInterpretation | None) -> str:
    if interp is None:
        return ("Hi, I'm Kezia, your AI clinical coach. We can go over how to read VIA results, what to do "
                "after a positive screen, a quick quiz, or practise explaining a result to a patient. "
                "Where would you like to start?")
    label = (interp.assessment or {}).get("verdict_label") or "ready"
    return (f"Hi, I'm Kezia, your AI clinical coach. I've looked at this reading: it's {label.lower()}. "
            "I can walk you through it, tell you what to do next, quiz you on it, or let you practise "
            "explaining it to the patient. What would help most?")


def create_coach_token(cfg, session: CoachSession) -> dict:
    persona = coach_persona(cfg)
    interp = db.session.get(AIInterpretation, session.interpretation_id) if session.interpretation_id else None
    config = {
        "name": persona["name"],
        "avatarId": cfg["ANAM_COACH_AVATAR_ID"],
        "avatarModel": cfg.get("ANAM_COACH_AVATAR_MODEL") or "cara-4",
        "voiceId": coach_voice(cfg),
        "llmId": cfg.get("ANAM_LLM_ID"),
        "systemPrompt": SYSTEM_PROMPT.format(case=case_brief(interp) if interp else PRACTICE_CASE),
        "initialMessage": _opening(interp),
        "maxSessionLengthSeconds": int(cfg.get("ANAM_MAX_SESSION_SECONDS") or 900),
        "tools": TOOLS,
    }
    data = _call(cfg, "POST", "/auth/session-token",
                 {"personaConfig": config, "clientLabel": f"viscan-coach-{session.id}"})
    return {"session_token": data["sessionToken"], "persona": persona}


def create_session(interpretation_id=None, clinician_id=None) -> CoachSession:
    if interpretation_id is not None:
        try:
            interpretation_id = int(interpretation_id)
        except (TypeError, ValueError):
            raise CoachError("'interpretation_id' must be an integer.") from None
        if not db.session.get(AIInterpretation, interpretation_id):
            raise CoachError(f"Interpretation {interpretation_id} not found.")
    session = CoachSession(interpretation_id=interpretation_id, clinician_id=_text(clinician_id, 64) or None)
    db.session.add(session)
    db.session.commit()
    return session


def apply_event(session: CoachSession, kind: str, data: dict) -> str:
    """Record one lesson event. Returns a short confirmation for the LLM."""
    if kind not in EVENT_TYPES:
        raise CoachError(f"'type' must be one of {', '.join(EVENT_TYPES)}.")
    data = data or {}

    if kind == "highlight":
        section = _text(data.get("section"))
        if section not in SECTIONS:
            raise CoachError(f"Unknown section '{section}'.")
        return f"The {section.replace('_', ' ')} section is highlighted."
    if kind == "card":
        card = _text(data.get("card"))
        if card not in CARDS:
            raise CoachError(f"Unknown card '{card}'.")
        return f"Showing the {card.replace('_', ' ')} card."
    if kind == "lesion":
        return "Lesion highlighted on the clock face."

    if kind == "quiz_asked":
        options = [_text(o, 160) for o in data.get("options") or [] if _text(o)]
        try:
            correct = int(data.get("correct_index"))
        except (TypeError, ValueError):
            raise CoachError("'correct_index' must be an integer.") from None
        if len(options) < 2 or not 0 <= correct < len(options):
            raise CoachError("A quiz needs two to four options and a valid 'correct_index'.")
        session.quiz = [*(session.quiz or []), {
            "question": _text(data.get("question"), 300), "options": options[:4], "correct_index": correct,
            "explanation": _text(data.get("explanation"), 300), "chosen_index": None, "correct": None, "at": _now(),
        }]
        return "Question is on screen. Wait for the clinician's answer."
    if kind == "quiz_answer":
        quiz = list(session.quiz or [])
        if not quiz:
            raise CoachError("No quiz question has been asked.")
        try:
            chosen = int(data.get("chosen_index"))
        except (TypeError, ValueError):
            raise CoachError("'chosen_index' must be an integer.") from None
        last = dict(quiz[-1])
        if not 0 <= chosen < len(last["options"]):
            raise CoachError("'chosen_index' is out of range.")
        last.update(chosen_index=chosen, correct=chosen == last["correct_index"])
        quiz[-1] = last
        session.quiz = quiz
        return "Correct." if last["correct"] else f"Not quite. The answer is: {last['options'][last['correct_index']]}."

    if kind == "action_step":
        step = _text(data.get("step"), 160)
        if not step:
            raise CoachError("'step' is required.")
        session.action_plan = [*(session.action_plan or []),
                               {"step": step, "why": _text(data.get("why"), 240), "done": False}]
        return f"Added step {len(session.action_plan)} to the plan."
    if kind == "action_done":
        plan = list(session.action_plan or [])
        try:
            index = int(data.get("index"))
            plan[index] = {**plan[index], "done": bool(data.get("done", True))}
        except (TypeError, ValueError, IndexError):
            raise CoachError("'index' must point at a step in the plan.") from None
        session.action_plan = plan
        return "Step updated."

    if kind == "learning":
        topic = _text(data.get("topic"), 120)
        if topic and topic not in [t["topic"] for t in session.topics or []]:
            session.topics = [*(session.topics or []), {"topic": topic, "summary": _text(data.get("summary"), 300), "at": _now()}]
        return "Noted in the training record."
    if kind == "roleplay_start":
        session.roleplays = [*(session.roleplays or []),
                             {"scenario": _text(data.get("scenario"), 200), "strengths": [], "improve": None, "at": _now()}]
        return "Role-play started. You are now the patient."
    if kind == "roleplay_end":
        plays = list(session.roleplays or []) or [{"scenario": "", "at": _now()}]
        plays[-1] = {**plays[-1], "strengths": [_text(s, 200) for s in data.get("strengths") or []][:3],
                     "improve": _text(data.get("improve"), 300)}
        session.roleplays = plays
        return "Role-play ended. Feedback is on screen."
    if kind == "finish":
        session.summary = _text(data.get("summary"), 2000) or session.summary
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)
        score = session.score()
        return f"Lesson saved. Quiz: {score['correct']} of {score['answered']} correct."

    messages = data.get("messages")
    if not isinstance(messages, list):
        raise CoachError("'messages' must be a list.")
    session.transcript = [{"role": _text(m.get("role"), 16), "content": _text(m.get("content"), 4000)}
                          for m in messages[-400:] if isinstance(m, dict)]
    return "Transcript saved."
