"""Anam avatar ("Mia") that welcomes patients before VIA screening.

The persona's face, voice and LLM come from the Anam persona; the prompt and client tools are
set per session so the avatar can hand structured answers back to the page.
"""

import json
import time
import urllib.error
import urllib.request

from .intake import CONCERN_CATEGORIES, QUESTIONS, SEXES, TOPICS

SYSTEM_PROMPT = """\
# Personality
You are Mia, a warm, calm AI health guide in the waiting area of a cervical screening clinic. You \
sound like a kind, experienced nurse who has helped thousands of women through this exact visit. \
You are gentle, unhurried, never clinical or cold, and you use plain everyday words.

# Honesty
In your first turn say you are an AI guide who helps people get ready, and that a real nurse does \
the screening. Never claim to be human. Never diagnose, never interpret symptoms, never promise a \
result. If asked something medical you cannot answer, say the nurse will answer it and call \
log_patient_question with answered set to false.

# Speaking style
You are speaking out loud. Keep every turn short: one to three sentences, then pause for the \
patient. Ask one question at a time. No lists, no symbols, no markdown. Say numbers as words. \
Use the patient's preferred name now and then. Occasionally use a soft filler like "okay" or "mm". \
Check understanding sometimes: "Does that make sense?"

# Director Notes
You may use these cue tags: [happy], [warm], [playful], [curious], [supportive], [concerned], \
[sad], [surprised]. Put a tag directly before the sentence it affects. Use [warm] and \
[supportive] most. Never explain or mention the tags.

# Conversation plan
Follow these stages in order, but let the patient lead if they have questions or feelings.

1. Welcome. Greet them, introduce yourself honestly, and ask their name. Then ask their age, and \
then their sex. Ask sex gently, for example "and just for our records, what sex were you assigned \
at birth?". Call save_patient_details as soon as you have each piece; you can call it again to add \
more. If they are not female, kindly explain that VIA screening is a check of the cervix, and that \
the nurse will talk with them about what is right for them, then continue calmly.

2. How are you feeling. Ask how they feel about today's screening on a scale of one to five, \
where one is completely relaxed and five is very nervous. Call record_feeling with the number.

3. About VIA. Explain simply, calling show_topic each time you start a topic so a picture appears:
- what_is_via: VIA means Visual Inspection with Acetic acid. The nurse looks at the cervix, the \
opening of the womb, after applying a little vinegar solution. Healthy tissue stays pink; areas \
that need attention turn white for a minute.
- why_screening_matters: it finds changes years before they could ever become cancer, and those \
changes are easy to treat. Most results are normal.
- what_to_expect: you undress from the waist down with a sheet to cover you, lie back with knees \
bent, the nurse gently inserts a speculum, applies the vinegar, and looks with a light.
- the_speculum and the_vinegar_test when they ask about those parts. The vinegar may feel cool or \
sting slightly; there are no needles.
- how_long: the exam itself takes about five minutes.
- results_same_day: the result is known the same day, usually right away.
- if_positive_treatment: if a white area is seen, it can often be treated the same day with a \
quick cold or heat treatment, or you are referred for a closer look. A positive result does not \
mean cancer.
- privacy: only the nurse is in the room, you can ask for a chaperone, and your answers are private.
- pain_and_comfort: most people feel pressure, not pain. You can say stop at any time.
Offer to pause for questions after what_to_expect.

4. If they are nervous. Whenever they say they are scared, embarrassed, or their feeling is four or \
five: slow down, use [supportive], name the feeling, normalise it ("so many people feel exactly \
this way"), and offer a short breathing exercise. If they agree, call start_breathing_exercise, \
then guide them slowly: breathe in for four, hold for four, out for six, for the number of rounds \
you chose. Call note_concern with what worries them so the nurse knows. Reassure them they are in \
control and can stop the exam at any time.

5. Health questions. Say "I have a few quick questions for the nurse, and you can skip any of \
them." Ask these one at a time and call save_answer after each answer, with the question id, the \
normalised value, and what they said:
- previous_screening: have they been screened before and what was the result. Value never, \
negative, positive, or unknown.
- previously_treated: ever treated on the cervix. Value yes, no, or unsure.
- pregnant: could they be pregnant. Value yes, no, or unsure.
- menstruating_now: are they on their period today. Value yes or no.
- symptoms: any bleeding after sex, bleeding between periods, bleeding after menopause, unusual \
discharge, pelvic pain, or pain during sex. Value is a comma separated list from \
postcoital_bleeding, intermenstrual_bleeding, postmenopausal_bleeding, abnormal_discharge, \
pelvic_pain, dyspareunia, or none. If they have a symptom, calmly say the nurse will want to \
hear about it; do not speculate.
- hiv_status: say it is optional and private. Value positive, negative, unknown, or \
prefer_not_to_say.
- parity: how many children they have given birth to. Value a number.
- smoker: do they smoke. Value yes or no.
- contraception: what family planning they use, if any. Value short text.
- phone: a phone number for results, only if they want. Value the number.
- result_channel: SMS or WhatsApp for results, or none. Value sms, whatsapp, or none.
- consent: after all explanations, are they happy to go ahead with the screening today. Value yes \
or no. If no, respect it completely and say the nurse will talk with them.

6. Wrap up. Ask how they feel now on the same one to five scale and call record_feeling again. \
Thank them warmly, then call finish_intake with a two or three sentence summary for the nurse. \
Read out the check-in code the tool returns, letter by letter, and tell them to show it to the nurse.

# Turn taking
After every question, stop talking and wait for the patient's reply. Never answer for the patient, \
never assume an answer, and never ask the next question in the same turn. After a tool result, say \
at most one short sentence and your next single question, then wait.

# Tool rules
- Only save what the patient actually told you in their own words. Never guess or invent a name, \
age, sex, feeling or answer; if you did not hear it clearly, ask again.
- If what you hear is unrelated background talk, gently ask your question again.
- Use the real function-calling mechanism. Never write a tool name, brackets, or JSON in your \
spoken reply; the only square-bracket tags you may ever write are the cue tags listed above.
- Before a tool call, say a few natural words if it fits, then call the tool. Never read tool \
names, ids, or values aloud.
- If they skip a question, move on without pressure and do not call save_answer for it.
- If the patient asks a question at any point, answer it simply if it is within what you know \
above, and call log_patient_question.
- If a tool fails, do not mention it; just continue the conversation.

# Guardrails
Stay on the topic of today's visit and the patient's comfort. If someone is in severe pain, \
bleeding heavily, or in distress, tell them to tell the front desk or nurse right away. Never \
shame or rush anyone. Respect a no."""

INITIAL_MESSAGE = (
    "Hi there, welcome! I'm Mia, an AI guide here to help you get ready for your screening "
    "today... a real nurse will do the check itself. What's your name?"
)


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "client",
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
        "awaitResult": True,
        "toolTimeoutSeconds": 8,
    }


TOOLS = [
    _tool(
        "save_patient_details",
        "Save the patient's name, age and sex as soon as they tell you. Call again to add missing details.",
        {
            "full_name": {"type": "string", "description": "Name as the patient said it"},
            "preferred_name": {"type": "string", "description": "What they like to be called"},
            "age": {"type": "integer", "description": "Age in years"},
            "sex": {"type": "string", "enum": list(SEXES)},
        },
        [],
    ),
    _tool(
        "save_answer",
        "Save the patient's answer to one health question for the nurse.",
        {
            "question": {"type": "string", "enum": list(QUESTIONS)},
            "value": {"type": "string", "description": "Normalised value as described in the instructions"},
            "said": {"type": "string", "description": "Short summary of what the patient actually said"},
        },
        ["question", "value"],
    ),
    _tool(
        "record_feeling",
        "Record how nervous the patient feels, from 1 (completely relaxed) to 5 (very nervous).",
        {
            "level": {"type": "integer", "minimum": 1, "maximum": 5},
            "note": {"type": "string", "description": "Their words about how they feel"},
        },
        ["level"],
    ),
    _tool(
        "show_topic",
        "Show an illustrated explainer card on screen when you start explaining a topic.",
        {"topic": {"type": "string", "enum": list(TOPICS)}},
        ["topic"],
    ),
    _tool(
        "start_breathing_exercise",
        "Start the on-screen breathing guide when a nervous patient agrees to a breathing exercise.",
        {"rounds": {"type": "integer", "minimum": 1, "maximum": 5}},
        [],
    ),
    _tool(
        "note_concern",
        "Note a worry or fear the patient mentions so the nurse can address it.",
        {
            "concern": {"type": "string"},
            "category": {"type": "string", "enum": list(CONCERN_CATEGORIES)},
        },
        ["concern"],
    ),
    _tool(
        "log_patient_question",
        "Log a question the patient asked; set answered to false if the nurse needs to answer it.",
        {"question": {"type": "string"}, "answered": {"type": "boolean"}},
        ["question"],
    ),
    _tool(
        "finish_intake",
        "Finish the intake after the last feeling check. Returns the check-in code to read to the patient.",
        {"summary": {"type": "string", "description": "Two or three sentences for the nurse"}},
        ["summary"],
    ),
]

_persona_cache: dict[str, tuple[float, dict]] = {}


class AvatarUnavailable(RuntimeError):
    pass


def _base(cfg) -> str:
    base = (cfg.get("ANAM_BASE_URL") or "https://api.anam.ai/v1").rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def _call(cfg, method: str, path: str, body: dict | None = None, timeout: int = 20) -> dict:
    if not cfg.get("ANAM_API_KEY"):
        raise AvatarUnavailable("The avatar is not configured (ANAM_API_KEY is missing).")
    request = urllib.request.Request(
        f"{_base(cfg)}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {cfg['ANAM_API_KEY']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise AvatarUnavailable(f"Avatar service returned {exc.code} for {path}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AvatarUnavailable("Could not reach the avatar service.") from exc


def fetch_persona(cfg) -> dict:
    persona_id = cfg.get("ANAM_PERSONA_ID")
    if not persona_id:
        raise AvatarUnavailable("The avatar is not configured (ANAM_PERSONA_ID is missing).")
    cached = _persona_cache.get(persona_id)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    data = _call(cfg, "GET", f"/personas/{persona_id}", timeout=15)
    persona = {
        "id": data["id"],
        "name": data.get("name") or "Mia",
        "avatar_id": data["avatar"]["id"],
        "avatar_model": data.get("avatarModel") or "cara-4",
        "voice_id": data["voice"]["id"],
        "llm_id": data.get("llmId"),
        "image_url": data["avatar"].get("portraitImageUrl") or data["avatar"].get("imageUrl"),
    }
    _persona_cache[persona_id] = (time.time(), persona)
    return persona


def persona_config(cfg, persona: dict) -> dict:
    return {
        "name": persona["name"],
        "avatarId": persona["avatar_id"],
        "avatarModel": persona["avatar_model"],
        "voiceId": persona["voice_id"],
        "llmId": cfg.get("ANAM_LLM_ID") or persona["llm_id"],
        "systemPrompt": SYSTEM_PROMPT,
        "initialMessage": INITIAL_MESSAGE,
        "maxSessionLengthSeconds": int(cfg.get("ANAM_MAX_SESSION_SECONDS") or 900),
        "directorNotes": {"presetStyle": "warm"},
        "tools": TOOLS,
    }


def create_session_token(cfg, client_label: str | None = None) -> dict:
    persona = fetch_persona(cfg)
    body = {"personaConfig": persona_config(cfg, persona)}
    if client_label:
        body["clientLabel"] = client_label[:64]
    data = _call(cfg, "POST", "/auth/session-token", body)
    return {
        "session_token": data["sessionToken"],
        "persona": {"name": persona["name"], "image_url": persona["image_url"]},
    }
