import io
import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from app import create_app
from app.services import interpreter as interp_mod
from app.services.rules import build_recommendation


def openai_result(via_result="VIA_POSITIVE", confidence=0.8, tz="type_1", area=30, red_flags=None,
                  swede=None, histology=None, lesions=None):
    flags = {"mass_or_exophytic_growth": False, "ulceration": False, "contact_bleeding": False,
             "atypical_vessels": False, "necrosis": False, "irregular_contour": False}
    flags.update(red_flags or {})
    return {
        "image_modality": "acetic_acid",
        "via_result": via_result, "confidence": confidence,
        "image_adequacy": {"adequate": True, "issues": []},
        "image_quality": {"cervix_fully_visible": True, "focus": "good", "lighting": "good",
                          "glare": "mild", "obscured_by": ["none"]},
        "scj_visibility": "fully_visible", "transformation_zone_type": tz,
        "findings": {"acetowhite_present": True, "acetowhite_density": "dense", "lesion_margins": "sharp",
                     "lesion_clock_positions": [12, 1, 2], "cervix_area_involved_percent": area,
                     "extends_into_canal": False, "other_findings": []},
        "lesions": lesions if lesions is not None else [{
            "clock_start": 12, "clock_end": 2, "area_percent": area, "density": "dense", "margins": "sharp",
            "surface": "smooth", "vessel_pattern": "fine_punctation", "touches_scj": True,
            "extends_into_canal": False, "bbox": {"x": 0.4, "y": 0.2, "width": 0.3, "height": 0.25},
            "description": "Dense acetowhite plaque at the SCJ.",
        }],
        "cancer_red_flags": flags,
        "benign_findings": ["ectropion"],
        "swede": swede or {"acetowhiteness": 2, "margins_surface": 1, "vessels": 0, "lesion_size": 1},
        "histology_likelihood": histology or {"normal_or_benign": 0.2, "cin1": 0.3, "cin2_plus": 0.45, "invasive_cancer": 0.05},
        "differential": [{"diagnosis": "CIN2/3", "likelihood": "moderate"}],
        "key_observations": ["Dense acetowhite area at 12-2 o'clock touching the SCJ."],
        "recommended_checks": ["Confirm the lesion does not enter the canal."],
        "patient_explanation": "We saw a small area that needs treatment.",
        "rationale": "Dense acetowhite epithelium at the SCJ.",
    }


def install_fake_openai(monkeypatch, result, captured=None):
    class FakeCompletions:
        def create(self, **kwargs):
            if captured is not None:
                captured.update(kwargs)
            msg = SimpleNamespace(content=json.dumps(result), refusal=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    class FakeOpenAI:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)


def cervix_image(acetowhite: bool, size=600) -> bytes:
    img = Image.new("RGB", (size, size), (120, 40, 50))
    draw = ImageDraw.Draw(img)
    draw.ellipse((80, 80, size - 80, size - 80), fill=(215, 120, 125))
    draw.ellipse((size / 2 - 20, size / 2 - 12, size / 2 + 20, size / 2 + 12), fill=(90, 30, 40))
    if acetowhite:
        draw.pieslice((140, 140, size - 140, size - 140), start=-90, end=0, fill=(238, 232, 228))
    img = img.filter(ImageFilter.GaussianBlur(1))
    noise = np.random.default_rng(0).normal(0, 6, (size, size, 3))
    img = Image.fromarray(np.clip(np.asarray(img) + noise, 0, 255).astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_DIR": tmp_path,
        "INTERPRETER_MODE": "heuristic",
        "API_KEY": "",
    })
    return app.test_client()


def upload(client, data: bytes, **fields):
    form = {"image": (io.BytesIO(data), "via.jpg"), **fields}
    return client.post("/api/v1/interpret", data=form, content_type="multipart/form-data")


def test_negative_and_positive_images(client):
    neg = upload(client, cervix_image(False), patient_external_id="P1", age="34", hiv_status="negative")
    assert neg.status_code == 201, neg.json
    assert neg.json["diagnosis"]["via_result"] == "VIA_NEGATIVE"
    assert neg.json["recommendation"]["follow_up_months"] == 36

    pos = upload(client, cervix_image(True), patient_external_id="P2", age="41", hiv_status="positive")
    body = pos.json
    assert body["diagnosis"]["via_result"] == "VIA_POSITIVE"
    assert body["findings"]["lesion_clock_positions"]
    assert set(body["findings"]["lesion_clock_positions"]) <= {12, 1, 2, 3}
    assert body["verdict"]["screening_verdict"] == "SUSPICIOUS"
    assert neg.json["verdict"]["screening_verdict"] == "NOT_SUSPICIOUS"
    assert any("HIV" in f for f in body["recommendation"]["flags"])
    assert body["recommendation"]["requires_clinician_confirmation"] is True


def test_quality_gate_rejects_tiny_image(client):
    buf = io.BytesIO()
    Image.new("RGB", (120, 120), (200, 100, 100)).save(buf, format="PNG")
    res = upload(client, buf.getvalue())
    assert res.status_code == 201
    assert res.json["diagnosis"]["via_result"] == "INADEQUATE"
    assert res.json["engine"]["name"] == "quality_gate"


def test_rejects_non_image(client):
    res = upload(client, b"not an image")
    assert res.status_code == 400


def test_full_feedback_loop_and_metrics(client):
    res = upload(client, cervix_image(True), patient_external_id="P3", age="38")
    interp_id, patient_id, image_id = res.json["interpretation_id"], res.json["patient_id"], res.json["image_id"]

    ann = client.post(f"/api/v1/interpretations/{interp_id}/annotations",
                      json={"clinician_id": "nurse-7", "via_result": "VIA_POSITIVE", "lesion_clock_positions": [1, 2]})
    assert ann.status_code == 201 and ann.json["agrees_with_ai"] is True

    dx = client.post(f"/api/v1/patients/{patient_id}/diagnoses",
                     json={"method": "histology", "result": "CIN2", "image_id": image_id, "diagnosed_on": "2026-09-01"})
    assert dx.status_code == 201

    out = client.post(f"/api/v1/patients/{patient_id}/outcomes",
                      json={"treatment": "thermal_ablation", "treated_on": "2026-09-01", "status": "open"})
    assert out.status_code == 201

    m = client.get("/api/v1/metrics").json
    assert m["clinician_agreement"]["agreement_rate"] == 1.0
    assert m["vs_histology_cin2_plus"]["true_positive"] == 1
    assert m["vs_histology_cin2_plus"]["sensitivity"] == 1.0

    record = client.get(f"/api/v1/patients/{patient_id}").json
    assert record["diagnoses"][0]["result"] == "CIN2"
    assert record["images"][0]["interpretations"][0]["annotations"][0]["clinician_id"] == "nurse-7"

    export = client.get("/api/v1/dataset/export")
    rows = [json.loads(line) for line in export.data.decode().splitlines()]
    assert rows[0]["clinician_annotations"][0]["via_result"] == "VIA_POSITIVE"


def test_validation_errors(client):
    res = upload(client, cervix_image(False), hiv_status="maybe")
    assert res.status_code == 400
    res = client.post("/api/v1/interpretations/999/annotations", json={"clinician_id": "x", "via_result": "VIA_NEGATIVE"})
    assert res.status_code == 404


def test_api_key_enforced(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "UPLOAD_DIR": tmp_path,
                      "INTERPRETER_MODE": "heuristic", "API_KEY": "secret"})
    c = app.test_client()
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/metrics").status_code == 401
    assert c.get("/api/v1/metrics", headers={"X-API-Key": "secret"}).status_code == 200


def test_rules_ablation_eligibility():
    base = {"via_result": "VIA_POSITIVE", "confidence": 0.9, "transformation_zone_type": "type_1",
            "scj_visibility": "fully_visible",
            "findings": {"cervix_area_involved_percent": 30, "extends_into_canal": False, "lesion_margins": "sharp"}}
    assert build_recommendation(base, {}, 0.75)["ablation_eligible"] is True

    big = {**base, "findings": {**base["findings"], "cervix_area_involved_percent": 80}}
    assert build_recommendation(big, {}, 0.75)["ablation_eligible"] is False

    canal = {**base, "transformation_zone_type": "type_3"}
    assert build_recommendation(canal, {}, 0.75)["ablation_eligible"] is False

    cancer = {**base, "via_result": "SUSPICIOUS_FOR_CANCER"}
    rec = build_recommendation(cancer, {}, 0.75)
    assert rec["urgency"] == "urgent" and rec["ablation_eligible"] is False


def test_openai_interpreter_uses_structured_output_and_references(client, monkeypatch):
    captured = {}
    fake_result = openai_result(
        via_result="SUSPICIOUS_FOR_CANCER", confidence=0.82, tz="type_3",
        red_flags={"mass_or_exophytic_growth": True, "ulceration": True},
        swede={"acetowhiteness": 2, "margins_surface": 2, "vessels": 2, "lesion_size": 2},
        histology={"normal_or_benign": 0.05, "cin1": 0.05, "cin2_plus": 0.3, "invasive_cancer": 0.6},
    )

    install_fake_openai(monkeypatch, fake_result, captured)

    first = upload(client, cervix_image(True), patient_external_id="P9")
    client.post(f"/api/v1/interpretations/{first.json['interpretation_id']}/annotations",
                json={"clinician_id": "dr-a", "via_result": "VIA_POSITIVE"})

    client.application.config.update(INTERPRETER_MODE="openai", OPENAI_API_KEY="sk-test")
    res = upload(client, cervix_image(True, size=640), patient_external_id="P10", age="52")
    body = res.json
    assert res.status_code == 201, body
    assert body["diagnosis"]["via_result"] == "SUSPICIOUS_FOR_CANCER"
    assert body["recommendation"]["urgency"] == "urgent"
    assert body["engine"]["reference_examples"] == [first.json["image_id"]]
    assert captured["response_format"]["json_schema"]["strict"] is True
    images_sent = [c for c in captured["messages"][1]["content"] if c["type"] == "image_url"]
    assert len(images_sent) == 2
    assert interp_mod.SYSTEM_PROMPT in captured["messages"][0]["content"]
    assert body["verdict"]["screening_verdict"] == "SUSPICIOUS"
    assert body["verdict"]["suspicion_level"] == "very_high"
    assert body["swede"]["total"] == 8
    assert body["treatment_eligibility"]["checklist"][0]["met"] is False


@pytest.fixture
def openai_client(client, monkeypatch):
    client.application.config.update(INTERPRETER_MODE="openai", OPENAI_API_KEY="sk-test")
    return client


def test_rich_response_is_returned_and_stored(openai_client, monkeypatch):
    install_fake_openai(monkeypatch, openai_result())
    res = upload(openai_client, cervix_image(True), patient_external_id="R1", age="36", hiv_status="positive",
                 hpv_status="positive", symptoms="postcoital_bleeding", pregnant="false", parity="2",
                 smoker="yes", previously_treated="no")
    assert res.status_code == 201, res.json
    body = res.json

    assert body["verdict"]["screening_verdict"] == "SUSPICIOUS"
    assert body["verdict"]["is_suspicious"] is True
    assert body["verdict"]["risk_score"] >= 45
    factors = " ".join(b["factor"] for b in body["risk_index"]["breakdown"])
    assert "HIV" in factors and "HPV" in factors and "bleeding" in factors
    assert body["swede"]["total"] == 4
    assert body["recommendation"]["ablation_eligible"] is True
    assert all(c["met"] for c in body["treatment_eligibility"]["checklist"])
    assert body["follow_up_due"]
    assert body["history"]["trend"] == "first_screen_on_record"
    assert body["visit"]["symptoms"] == ["postcoital_bleeding"]
    assert body["visit"]["smoker"] is True and body["visit"]["parity"] == 2
    assert body["lesions"][0]["vessel_pattern"] == "fine_punctation"
    assert body["clinical_summary"]["patient_explanation"]
    assert any("canal" in c for c in body["clinical_summary"]["clinician_checklist"])

    stored = openai_client.get(f"/api/v1/interpretations/{body['interpretation_id']}").json
    assert stored["verdict"] == body["verdict"]
    assert stored["lesions"][0]["id"]

    overlay = openai_client.get(body["links"]["overlay"])
    assert overlay.status_code == 200 and overlay.mimetype == "image/png"
    report = openai_client.get(body["links"]["report"])
    assert report.status_code == 200 and b"SUSPICIOUS" in report.data and b"Swede" in report.data


def test_symptomatic_negative_is_referred_and_history_tracked(openai_client, monkeypatch):
    install_fake_openai(monkeypatch, openai_result())
    upload(openai_client, cervix_image(True), patient_external_id="H1", age="40")

    negative = openai_result(via_result="VIA_NEGATIVE", area=0, lesions=[],
                             swede={"acetowhiteness": 0, "margins_surface": 0, "vessels": 0, "lesion_size": 0})
    install_fake_openai(monkeypatch, negative)
    res = upload(openai_client, cervix_image(False, size=640), patient_external_id="H1",
                 symptoms="postcoital_bleeding,abnormal_discharge")
    body = res.json
    assert body["verdict"]["screening_verdict"] == "NOT_SUSPICIOUS"
    assert body["recommendation"]["urgency"] == "soon"
    assert "refer" in body["recommendation"]["action"].lower()
    assert body["history"]["trend"] == "resolved_since_last_screen"
    assert len(body["history"]["previous_screens"]) == 1


def test_worklist_orders_by_suspicion_and_review_clears_it(openai_client, monkeypatch):
    install_fake_openai(monkeypatch, openai_result(via_result="VIA_NEGATIVE", lesions=[]))
    neg = upload(openai_client, cervix_image(False), patient_external_id="W1").json
    install_fake_openai(monkeypatch, openai_result(via_result="SUSPICIOUS_FOR_CANCER", red_flags={"ulceration": True}))
    sus = upload(openai_client, cervix_image(True), patient_external_id="W2").json

    rows = openai_client.get("/api/v1/worklist").json
    assert [r["interpretation_id"] for r in rows] == [sus["interpretation_id"], neg["interpretation_id"]]
    assert openai_client.get("/api/v1/worklist?verdict=NOT_SUSPICIOUS").json[0]["interpretation_id"] == neg["interpretation_id"]

    res = openai_client.post(sus["links"]["annotate"], json={"clinician_id": "dr-b", "via_result": "VIA_POSITIVE"})
    assert res.json["review_status"] == "disputed"
    pending = [r["interpretation_id"] for r in openai_client.get("/api/v1/worklist").json]
    assert pending == [neg["interpretation_id"]]

    metrics = openai_client.get("/api/v1/metrics").json
    assert metrics["by_verdict"] == {"NOT_SUSPICIOUS": 1, "SUSPICIOUS": 1}
    assert metrics["by_review_status"] == {"pending": 1, "disputed": 1}


def test_care_flow_partners_referral_notifications(openai_client, monkeypatch):
    install_fake_openai(monkeypatch, openai_result(tz="type_3", swede={"acetowhiteness": 2, "margins_surface": 2,
                                                                       "vessels": 1, "lesion_size": 2}))
    res = upload(openai_client, cervix_image(True), patient_external_id="C1").json
    interp_id = res["interpretation_id"]

    partners = openai_client.get("/api/v1/partner-hospitals?lat=-1.9441&lng=30.0619").json["results"]
    assert len(partners) == 4 and all(p["is_demo"] for p in partners)
    assert [p["distance_km"] for p in partners] == sorted(p["distance_km"] for p in partners)

    care = openai_client.get(f"/api/v1/interpretations/{interp_id}/care").json
    assert care["is_suspicious"] is True and care["needs_referral"] is True
    assert any("Pain relief" in s["item"] for s in care["suggested_supplies"])

    ref = openai_client.post(f"/api/v1/interpretations/{interp_id}/referrals",
                             json={"hospital_id": partners[0]["id"], "referred_by": "nurse-01"})
    assert ref.status_code == 201 and ref.json["hospital"]["name"] == partners[0]["name"]

    note = openai_client.post(f"/api/v1/interpretations/{interp_id}/notifications",
                              json={"channel": "whatsapp", "phone": "+250 788 123 456"})
    assert note.status_code == 201
    assert note.json["status"] == "simulated" and note.json["recipient"] == "+250788123456"
    assert partners[0]["name"] in note.json["message"] and "C1" in note.json["message"]

    care = openai_client.get(f"/api/v1/interpretations/{interp_id}/care").json
    assert len(care["referrals"]) == 1 and len(care["notifications"]) == 1

    bad = openai_client.post(f"/api/v1/interpretations/{interp_id}/notifications", json={"channel": "fax", "phone": "123"})
    assert bad.status_code == 400

    created = openai_client.post("/api/v1/partner-hospitals",
                                 json={"name": "Real Partner", "latitude": -1.95, "longitude": 30.06, "services": ["LEEP"]})
    assert created.status_code == 201 and created.json["is_demo"] is False
    only_leep = openai_client.get("/api/v1/partner-hospitals?service=LEEP").json["results"]
    assert "Real Partner" in [p["name"] for p in only_leep]


def test_pharmacies_from_openstreetmap(client, monkeypatch):
    from app.services import places

    places._CACHE.clear()
    monkeypatch.setattr(places, "_query", lambda urls, q: {"elements": [
        {"type": "node", "id": 1, "lat": -1.95, "lon": 30.07, "tags": {"name": "Far Pharmacy"}},
        {"type": "way", "id": 2, "center": {"lat": -1.9442, "lon": 30.0620},
         "tags": {"name": "Near Pharmacy", "opening_hours": "24/7", "phone": "+250 700"}},
    ]})
    res = client.get("/api/v1/places/pharmacies?lat=-1.9441&lng=30.0619&radius=2000")
    assert res.status_code == 200
    names = [p["name"] for p in res.json["results"]]
    assert names == ["Near Pharmacy", "Far Pharmacy"]
    assert res.json["results"][0]["osm_url"].endswith("/way/2")

    def boom(urls, q):
        raise places.PlacesUnavailable("down")

    places._CACHE.clear()
    monkeypatch.setattr(places, "_query", boom)
    assert client.get("/api/v1/places/pharmacies?lat=0&lng=0").status_code == 503


def test_invalid_symptom_rejected(client):
    res = upload(client, cervix_image(False), symptoms="headache")
    assert res.status_code == 400


def _event(client, intake_id, kind, **data):
    res = client.post(f"/api/v1/intake/{intake_id}/events", json={"type": kind, "data": data})
    assert res.status_code == 200, res.json
    return res.json


def test_avatar_intake_flow_prefills_screening(client):
    intake = client.post("/api/v1/intake", json={"language": "en"}).json
    iid, code = intake["id"], intake["code"]
    assert intake["status"] == "in_progress" and len(code) == 5

    _event(client, iid, "details", full_name="Grace Uwase", preferred_name="Grace", age="38 years", sex="Female")
    _event(client, iid, "feeling", level=5, note="very scared")
    _event(client, iid, "topic", topic="what_to_expect")
    _event(client, iid, "breathing", rounds=3)
    _event(client, iid, "concern", concern="Worried it will hurt", category="pain")
    _event(client, iid, "question", question="Can my sister come in?", answered=False)
    for question, value in [("previous_screening", "negative"), ("pregnant", "no"), ("menstruating_now", "yes"),
                            ("symptoms", "postcoital_bleeding, headache"), ("hiv_status", "positive"),
                            ("parity", "3 children"), ("smoker", "no"), ("phone", "+250 788 111 222"),
                            ("result_channel", "whatsapp"), ("consent", "yes")]:
        _event(client, iid, "answer", question=question, value=value, said=value)
    _event(client, iid, "feeling", level=2)
    done = _event(client, iid, "finish", summary="Grace was nervous about pain; calmer after breathing.")
    assert code in done["message"]
    _event(client, iid, "transcript", messages=[{"role": "persona", "content": "Hi"}, {"role": "user", "content": "Hello"}])

    data = client.get(f"/api/v1/intake/{iid}?transcript=1").json
    assert data["status"] == "completed" and data["age"] == 38 and data["sex"] == "female"
    assert data["anxiety"] == {"start": 5, "end": 2, "change": -3}
    assert data["breathing_exercises"] == 1 and data["topics_covered"] == ["what_to_expect"]
    assert len(data["transcript"]) == 2
    prefill = data["prefill"]
    assert prefill["patient_external_id"] == f"INT-{code}"
    assert prefill["hiv_status"] == "positive" and prefill["pregnant"] is False and prefill["parity"] == 3
    assert prefill["symptoms"] == ["postcoital_bleeding"] and prefill["previous_screening_result"] == "VIA_NEGATIVE"
    assert prefill["phone"] == "+250788111222" and prefill["result_channel"] == "whatsapp"
    flags = " ".join(f["text"] for f in data["flags"])
    assert "postcoital bleeding" in flags and "menstruating" in flags and "Can my sister come in?" in flags
    assert client.get(f"/api/v1/intake/code/{code.lower()}").json["id"] == iid

    res = upload(client, cervix_image(True), patient_external_id=prefill["patient_external_id"], intake_id=str(iid))
    assert res.status_code == 201 and res.json["intake_id"] == iid
    linked = client.get(f"/api/v1/intake/{iid}").json
    assert linked["interpretation_id"] == res.json["interpretation_id"]
    assert client.get("/api/v1/intake?unscreened=1").json == []


def test_intake_rejects_bad_events(client):
    iid = client.post("/api/v1/intake").json["id"]
    assert client.post(f"/api/v1/intake/{iid}/events", json={"type": "dance"}).status_code == 400
    assert client.post(f"/api/v1/intake/{iid}/events",
                       json={"type": "answer", "data": {"question": "favourite_colour", "value": "red"}}).status_code == 400
    assert client.post(f"/api/v1/intake/{iid}/events", json={"type": "feeling", "data": {"level": "calm"}}).status_code == 400


def test_avatar_token_uses_persona_with_intake_tools(client, monkeypatch):
    from app.services import avatar

    calls = []

    def fake_call(cfg, method, path, body=None, timeout=20):
        calls.append((method, path, body))
        if path.startswith("/personas/"):
            return {"id": "p1", "name": "Mia", "avatarModel": "cara-4", "llmId": "llm-1",
                    "avatar": {"id": "av-1", "imageUrl": "https://img"}, "voice": {"id": "vo-1"}}
        return {"sessionToken": "tok-123"}

    avatar._persona_cache.clear()
    monkeypatch.setattr(avatar, "_call", fake_call)
    client.application.config.update(ANAM_API_KEY="k", ANAM_PERSONA_ID="p1", ANAM_LLM_ID="")
    iid = client.post("/api/v1/intake").json["id"]
    res = client.post(f"/api/v1/intake/{iid}/avatar-token")
    assert res.status_code == 200 and res.json["session_token"] == "tok-123"
    config = calls[-1][2]["personaConfig"]
    assert config["avatarId"] == "av-1" and config["voiceId"] == "vo-1" and config["llmId"] == "llm-1"
    assert {t["name"] for t in config["tools"]} >= {"save_patient_details", "save_answer", "finish_intake"}
    assert all(t["type"] == "client" for t in config["tools"])

    client.application.config.update(ANAM_API_KEY="")
    avatar._persona_cache.clear()
    monkeypatch.undo()
    assert client.post(f"/api/v1/intake/{iid}/avatar-token").status_code == 503


def _coach(client, sid, kind, **data):
    res = client.post(f"/api/v1/coach/sessions/{sid}/events", json={"type": kind, "data": data})
    assert res.status_code == 200, res.json
    return res.json


def test_coach_lesson_records_quiz_plan_and_roleplay(client):
    interp_id = upload(client, cervix_image(True), patient_external_id="PT-COACH").json["interpretation_id"]
    session = client.post("/api/v1/coach/sessions", json={"interpretation_id": interp_id, "clinician_id": "nurse-07"})
    assert session.status_code == 201
    sid = session.json["id"]

    assert "findings" in _coach(client, sid, "highlight", section="findings")["message"]
    _coach(client, sid, "card", card="ablation_eligibility")
    _coach(client, sid, "quiz_asked", question="Is this VIA positive?", options=["Yes", "No"], correct_index=0,
           explanation="Dense acetowhite at the SCJ.")
    assert _coach(client, sid, "quiz_answer", chosen_index=0)["message"] == "Correct."
    _coach(client, sid, "quiz_asked", question="Ablate if TZ type 3?", options=["Yes", "No"], correct_index=1)
    assert "The answer is: No" in _coach(client, sid, "quiz_answer", chosen_index=0)["message"]
    _coach(client, sid, "action_step", step="Confirm the finding", why="AI is decision support")
    _coach(client, sid, "action_step", step="Counsel the patient")
    _coach(client, sid, "action_done", index=0)
    _coach(client, sid, "learning", topic="Swede score", summary="Six of eight suggests high grade")
    _coach(client, sid, "roleplay_start", scenario="Telling the patient her result")
    _coach(client, sid, "roleplay_end", strengths=["Clear", "Kind"], improve="Check understanding")
    done = _coach(client, sid, "finish", summary="Walked through the reading.")
    assert "1 of 2 correct" in done["message"]

    data = client.get(f"/api/v1/coach/sessions/{sid}").json
    assert data["status"] == "completed" and data["score"] == {"asked": 2, "answered": 2, "correct": 1}
    assert [s["done"] for s in data["action_plan"]] == [True, False]
    assert data["roleplays"][0]["improve"] == "Check understanding"
    assert data["topics"][0]["topic"] == "Swede score"
    assert client.get("/api/v1/coach/sessions?clinician_id=nurse-07").json[0]["id"] == sid


def test_coach_rejects_bad_input(client):
    assert client.post("/api/v1/coach/sessions", json={"interpretation_id": 999}).status_code == 400
    sid = client.post("/api/v1/coach/sessions", json={}).json["id"]
    bad = [{"type": "dance"}, {"type": "highlight", "data": {"section": "nowhere"}},
           {"type": "quiz_asked", "data": {"question": "?", "options": ["only one"], "correct_index": 0}},
           {"type": "quiz_answer", "data": {"chosen_index": 0}}]
    for body in bad:
        assert client.post(f"/api/v1/coach/sessions/{sid}/events", json=body).status_code == 400


def test_coach_token_briefs_the_case(client, monkeypatch):
    from app.services import coach

    calls = []

    def fake_call(cfg, method, path, body=None, timeout=20):
        calls.append((method, path, body))
        if path.startswith("/avatars/"):
            return {"id": "av-k", "portraitImageUrl": "https://img/kezia"}
        return {"sessionToken": "coach-tok"}

    coach._avatar_cache.clear()
    monkeypatch.setattr(coach, "_call", fake_call)
    client.application.config.update(ANAM_API_KEY="k", ANAM_COACH_AVATAR_ID="av-k", ANAM_COACH_VOICE_ID="vo-k")
    interp_id = upload(client, cervix_image(True), patient_external_id="PT-BRIEF", age="41").json["interpretation_id"]
    sid = client.post("/api/v1/coach/sessions", json={"interpretation_id": interp_id}).json["id"]

    res = client.post(f"/api/v1/coach/sessions/{sid}/token")
    assert res.status_code == 200 and res.json == {"session_token": "coach-tok",
                                                   "persona": {"name": "Kezia", "image_url": "https://img/kezia"}}
    config = calls[-1][2]["personaConfig"]
    assert config["avatarId"] == "av-k" and config["voiceId"] == "vo-k"
    assert f"Reading #{interp_id}" in config["systemPrompt"] and "age 41" in config["systemPrompt"]
    assert "Ablation eligible" in config["systemPrompt"] and "AI clinical coach" in config["initialMessage"]
    assert {t["name"] for t in config["tools"]} >= {"highlight_section", "ask_quiz", "start_roleplay", "add_action_step"}

    practice = client.post("/api/v1/coach/sessions", json={}).json["id"]
    client.post(f"/api/v1/coach/sessions/{practice}/token")
    assert "No specific reading is open" in calls[-1][2]["personaConfig"]["systemPrompt"]

    client.application.config.update(ANAM_API_KEY="")
    coach._avatar_cache.clear()
    monkeypatch.undo()
    assert client.post(f"/api/v1/coach/sessions/{sid}/token").status_code == 503


def test_past_screenings_history(client):
    first = upload(client, cervix_image(True), patient_external_id="PT-HIST-1", site="Kigali HC").json
    second = upload(client, cervix_image(False), patient_external_id="PT-HIST-2").json
    client.post(f"/api/v1/interpretations/{first['interpretation_id']}/annotations",
                json={"clinician_id": "nurse-07", "via_result": "VIA_POSITIVE", "notes": "Dense lesion at 3"})
    hospital = client.get("/api/v1/partner-hospitals").json["results"][0]
    client.post(f"/api/v1/interpretations/{first['interpretation_id']}/referrals", json={"hospital_id": hospital["id"]})
    client.post(f"/api/v1/interpretations/{first['interpretation_id']}/notifications",
                json={"channel": "sms", "phone": "+250788000111"})

    data = client.get("/api/v1/screenings").json
    assert data["total"] == 2 and data["pages"] == 1
    assert [i["interpretation_id"] for i in data["items"]] == [second["interpretation_id"], first["interpretation_id"]]
    row = data["items"][1]
    assert row["patient_external_id"] == "PT-HIST-1" and row["site"] == "Kigali HC"
    assert row["result_source"] == "clinician" and row["confirmed_by"] == "nurse-07"
    assert row["clinician_notes"] == "Dense lesion at 3" and row["notifications"] == 1
    assert row["referral"]["hospital"] == hospital["name"]
    assert data["summary"]["total"] == 2 and data["summary"]["referred"] == 1

    assert client.get("/api/v1/screenings?q=HIST-2").json["total"] == 1
    assert client.get(f"/api/v1/screenings?q=%23{first['interpretation_id']}").json["items"][0]["patient_external_id"] == "PT-HIST-1"
    assert client.get("/api/v1/screenings?referred=1").json["total"] == 1
    assert client.get("/api/v1/screenings?status=reviewed").json["total"] == 1
    assert client.get("/api/v1/screenings?per_page=1&page=2").json["items"][0]["interpretation_id"] == first["interpretation_id"]
    assert client.get("/api/v1/screenings?from=2000-01-01&to=2000-12-31").json["total"] == 0
    assert client.get("/api/v1/screenings?sort=sideways").status_code == 400
    assert client.get("/api/v1/screenings?from=yesterday").status_code == 400

    thumb = client.get(row["links"]["thumbnail"])
    assert thumb.status_code == 200 and thumb.mimetype == "image/jpeg"


# --- Video report (ai-avatar) after clinician confirmation -------------------

def test_confirmation_creates_video_report(tmp_path, monkeypatch):
    from app.services import video_report

    calls = []

    def fake_post(url, body, timeout):
        calls.append((url, body))
        return 201, {"id": "rep-1", "scan_id": body["scan_id"], "status": "ready"}

    monkeypatch.setattr(video_report, "_post_json", fake_post)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "UPLOAD_DIR": tmp_path,
                      "INTERPRETER_MODE": "heuristic", "API_KEY": "", "AVATAR_API_URL": "http://ai-avatar:9090"})
    client = app.test_client()

    res = upload(client, cervix_image(True), patient_external_id="P-VID", age="40", hiv_status="negative")
    assert res.status_code == 201, res.json
    interp_id = res.json["interpretation_id"]
    assert res.json["links"]["video_status"] == f"/api/v1/reports/viscan-{interp_id}/video"
    assert res.json["links"]["video_player"] == f"/player/viscan-{interp_id}"
    assert calls == []  # nothing is rendered before the clinician confirms

    ann = client.post(f"/api/v1/interpretations/{interp_id}/annotations",
                      json={"clinician_id": "DR-1", "via_result": "SUSPICIOUS_FOR_CANCER", "notes": "Refer today."})
    assert ann.status_code == 201, ann.json
    assert ann.json["video_report"] == {"scan_id": f"viscan-{interp_id}", "status": "created"}

    url, body = calls[0]
    assert url == "http://ai-avatar:9090/api/v1/reports"
    assert body["scan_id"] == f"viscan-{interp_id}"
    assert body["patient_id"] == "P-VID"
    assert body["clinician_id"] == "DR-1"
    # The APPROVED (clinician) result is what gets narrated, not the raw AI one.
    assert body["screening_result"].startswith("Suspicious for invasive cervical cancer")
    assert "corrected" in body["clinical_notes"] or "confirmed" in body["clinical_notes"]
    assert "Refer today." in body["clinical_notes"]
    assert body["recommendations"]
    assert 0 <= body["confidence_score"] <= 1


def test_video_report_failures_do_not_block_confirmation(tmp_path, monkeypatch):
    from app.services import video_report

    def failing_post(url, body, timeout):
        raise video_report.VideoReportError("down")

    monkeypatch.setattr(video_report, "_post_json", failing_post)
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "UPLOAD_DIR": tmp_path,
                      "INTERPRETER_MODE": "heuristic", "API_KEY": "", "AVATAR_API_URL": "http://ai-avatar:9090"})
    client = app.test_client()
    interp_id = upload(client, cervix_image(False)).json["interpretation_id"]
    ann = client.post(f"/api/v1/interpretations/{interp_id}/annotations",
                      json={"clinician_id": "DR-1", "via_result": "VIA_NEGATIVE"})
    assert ann.status_code == 201
    assert ann.json["review_status"] == "reviewed"
    assert ann.json["video_report"]["status"] == "failed"

    # 409 = report already exists (idempotent re-confirmation)
    monkeypatch.setattr(video_report, "_post_json", lambda u, b, t: (409, {"detail": "exists"}))
    again = client.post(f"/api/v1/interpretations/{interp_id}/annotations",
                        json={"clinician_id": "DR-2", "via_result": "VIA_NEGATIVE"})
    assert again.json["video_report"]["status"] == "exists"


def test_video_report_disabled_without_avatar_url(client):
    interp_id = upload(client, cervix_image(False)).json["interpretation_id"]
    ann = client.post(f"/api/v1/interpretations/{interp_id}/annotations",
                      json={"clinician_id": "DR-1", "via_result": "VIA_NEGATIVE"})
    assert ann.status_code == 201
    assert ann.json["video_report"]["status"] == "disabled"
