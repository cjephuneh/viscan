import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Facility


@pytest.fixture()
def app(tmp_path):
    application = create_app("testing")
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def facility(app):
    with app.app_context():
        item = Facility(name="District Hospital", type="District Hospital", is_active=True)
        db.session.add(item)
        db.session.commit()
        db.session.refresh(item)
        return item.id


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(20, 120, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_ok(client, facility):
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "connected"}


def test_create_and_get_screening(client, facility):
    create = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000001"},
    )
    assert create.status_code == 201
    body = create.get_json()
    assert body["status"] == "CREATED"
    assert body["patient_code"] == "VIA-000001"

    detail = client.get(f"/api/v1/screenings/{body['id']}/")
    assert detail.status_code == 200
    assert detail.get_json()["id"] == body["id"]


def test_duplicate_patient_code(client, facility):
    payload = {"facility_id": facility, "patient_code": "VIA-000002"}
    assert client.post("/api/v1/screenings/", json=payload).status_code == 201
    conflict = client.post("/api/v1/screenings/", json=payload)
    assert conflict.status_code == 409
    assert "detail" in conflict.get_json()


def test_missing_facility(client):
    response = client.post(
        "/api/v1/screenings/",
        json={"facility_id": 9999, "patient_code": "VIA-000099"},
    )
    assert response.status_code == 404
    assert response.get_json()["detail"] == "Facility not found."


def test_image_upload_and_workflow(client, facility, app):
    screening = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000010",
            "phone": "+250788000010",
            "notify_channel": "sms",
        },
    ).get_json()

    upload = client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    image = upload.get_json()
    assert image["media_type"] == "image/png"
    assert image["analysis_job"]["status"] == "queued"
    assert image["analysis_job"]["ahead"] == 0

    status = client.get(f"/api/v1/screenings/{screening['id']}/").get_json()["status"]
    assert status == "QUEUED"

    analyze = client.post(f"/api/v1/screenings/{screening['id']}/analyze/")
    assert analyze.status_code == 202
    assert analyze.get_json()["id"] == image["analysis_job"]["id"]

    ai_payload = {
        "prediction": "abnormal",
        "confidence": 0.91,
        "model_version": "v1.0",
        "processing_time_ms": 842,
        "recommendation": "Return for colposcopy within two weeks.",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ai_payload

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        with app.app_context():
            from app.services.queue_service import process_next

            assert process_next() is True

    job = client.get(f"/api/v1/analysis-jobs/{image['analysis_job']['id']}/")
    assert job.status_code == 200
    result = job.get_json()["ai_result"]
    assert result["prediction"] == "abnormal"
    assert result["confidence"] == 0.91
    assert result["recommendation"] == "Return for colposcopy within two weeks."

    stored = client.get(f"/api/v1/ai-results/{result['id']}/")
    assert stored.status_code == 200
    assert stored.get_json()["model_version"] == "v1.0"

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "abnormal", "notes": "Clinician confirmed"},
    )
    assert assessment.status_code == 201
    body = assessment.get_json()
    assert body["result"] == "abnormal"
    assert body["notification"]["channel"] == "sms"
    assert body["notification"]["positive"] is True
    assert "Return for colposcopy within two weeks." in body["notification"]["message"]
    assert body["notification"]["delivery"]["provider"] == "stub"

    final = client.get(f"/api/v1/screenings/{screening['id']}/")
    assert final.status_code == 200
    assert final.get_json()["status"] == "REVIEWED"
    assert final.get_json()["assessment"]["result"] == "abnormal"
    assert final.get_json()["phone"] == "+250788000010"

    resend = client.post(f"/api/v1/screenings/{screening['id']}/notify/")
    assert resend.status_code == 200
    assert resend.get_json()["positive"] is True


def test_patient_contact_requires_both_fields(client, facility):
    missing_channel = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000014",
            "phone": "+250788000014",
        },
    )
    assert missing_channel.status_code == 400
    assert "notify_channel" in missing_channel.get_json()["detail"]

    missing_phone = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000015",
            "notify_channel": "whatsapp",
        },
    )
    assert missing_phone.status_code == 400
    assert "phone" in missing_phone.get_json()["detail"]


def _queue_ai_result(client, app, screening_id, ai_payload):
    upload = client.post(
        f"/api/v1/screenings/{screening_id}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    job_id = upload.get_json()["analysis_job"]["id"]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ai_payload

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        with app.app_context():
            from app.services.queue_service import process_next

            assert process_next() is True

    job = client.get(f"/api/v1/analysis-jobs/{job_id}/").get_json()
    assert job["status"] == "completed"
    return job["ai_result"]


def test_patient_notify_whatsapp_with_recommendation(client, facility, app):
    screening = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000040",
            "phone": "+250788000040",
            "notify_channel": "whatsapp",
        },
    ).get_json()

    result = _queue_ai_result(
        client,
        app,
        screening["id"],
        {
            "prediction": "positive",
            "confidence": 0.88,
            "model_version": "v1.0",
            "processing_time_ms": 500,
            "recommendation": "Schedule colposcopy within 14 days.",
        },
    )
    assert result["recommendation"] == "Schedule colposcopy within 14 days."

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "positive", "notes": "Confirmed"},
    )
    assert assessment.status_code == 201
    body = assessment.get_json()
    assert body["notification"]["channel"] == "whatsapp"
    assert body["notification"]["to"] == "+250788000040"
    assert body["notification"]["positive"] is True
    assert "Schedule colposcopy within 14 days." in body["notification"]["message"]
    assert body["notification"]["delivery"]["provider"] == "stub"

    resend = client.post(f"/api/v1/screenings/{screening['id']}/notify/")
    assert resend.status_code == 200
    assert resend.get_json()["channel"] == "whatsapp"
    assert resend.get_json()["positive"] is True


def test_patient_notify_positive_uses_default_recommendation(client, facility, app):
    screening = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000041",
            "phone": "+250788000041",
            "notify_channel": "sms",
        },
    ).get_json()

    result = _queue_ai_result(
        client,
        app,
        screening["id"],
        {
            "prediction": "abnormal",
            "confidence": 0.8,
            "model_version": "v1.0",
            "processing_time_ms": 400,
        },
    )
    assert result.get("recommendation") in (None, "")

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "abnormal"},
    )
    assert assessment.status_code == 201
    notification = assessment.get_json()["notification"]
    assert notification["positive"] is True
    assert "Please return to your health facility for follow-up." in notification["message"]
    assert "Recommendation:" in notification["message"]


def test_patient_notify_normal_omits_recommendation(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={
            "facility_id": facility,
            "patient_code": "VIA-000042",
            "phone": "+250788000042",
            "notify_channel": "sms",
        },
    ).get_json()

    before = client.post(f"/api/v1/screenings/{screening['id']}/notify/")
    assert before.status_code == 400
    assert "Assessment is required" in before.get_json()["detail"]

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "normal", "notes": "Clear"},
    )
    assert assessment.status_code == 201
    notification = assessment.get_json()["notification"]
    assert notification["channel"] == "sms"
    assert notification["positive"] is False
    assert "Clinician result: normal." in notification["message"]
    assert "Recommendation:" not in notification["message"]

    resend = client.post(f"/api/v1/screenings/{screening['id']}/notify/")
    assert resend.status_code == 200
    assert resend.get_json()["positive"] is False
    assert "Recommendation:" not in resend.get_json()["message"]


def test_patient_notify_requires_contact(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000043"},
    ).get_json()

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "abnormal"},
    )
    assert assessment.status_code == 201
    assert assessment.get_json().get("notification") is None

    notify = client.post(f"/api/v1/screenings/{screening['id']}/notify/")
    assert notify.status_code == 400
    assert "phone and notify_channel" in notify.get_json()["detail"]


def test_analyze_without_image(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000011"},
    ).get_json()
    response = client.post(f"/api/v1/screenings/{screening['id']}/analyze/")
    assert response.status_code == 400
    assert response.get_json()["detail"] == "VIA image is required before analysis."


def test_invalid_image_rejected(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000012"},
    ).get_json()
    response = client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(b"not-an-image"), "via.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "detail" in response.get_json()


def test_ai_unavailable(client, facility, app):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000013"},
    ).get_json()
    upload = client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    job_id = upload.get_json()["analysis_job"]["id"]

    import httpx

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError(
            "down"
        )
        with app.app_context():
            from app.services.queue_service import process_next

            assert process_next() is True

    job = client.get(f"/api/v1/analysis-jobs/{job_id}/")
    assert job.status_code == 200
    assert job.get_json()["status"] == "failed"
    assert job.get_json()["error_detail"] == "AI service is unavailable."
    screening_status = client.get(f"/api/v1/screenings/{screening['id']}/").get_json()["status"]
    assert screening_status == "ANALYSIS_FAILED"


def test_notification_and_language_stubs(client):
    sms = client.post(
        "/api/v1/notifications/sms/",
        json={"to": "+250788000000", "message": "Screening completed"},
    )
    assert sms.status_code == 200
    assert sms.get_json()["provider"] == "stub"

    translated = client.post(
        "/api/v1/language/translate/",
        json={
            "text": "Screening completed",
            "source_language": "en",
            "target_language": "rw",
        },
    )
    assert translated.status_code == 200
    assert translated.get_json()["translated_text"] == "Screening completed"

    whatsapp = client.post(
        "/api/v1/notifications/whatsapp/",
        json={"to": "+250788000000", "message": "Screening completed"},
    )
    assert whatsapp.status_code == 200
    assert whatsapp.get_json()["provider"] == "stub"

    voice = client.post(
        "/api/v1/voice/synthesize/",
        json={"text": "Hello", "language": "en"},
    )
    assert voice.status_code == 200
    assert voice.get_json()["provider"] == "stub"


def test_create_facility(client):
    created = client.post(
        "/api/v1/facilities/",
        json={
            "name": "Health Centre",
            "type": "Health Centre",
            "latitude": -1.94,
            "longitude": 30.06,
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["name"] == "Health Centre"
    assert body["is_active"] is True

    listed = client.get("/api/v1/facilities/")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.get_json())


def test_missing_screening(client):
    missing = client.get("/api/v1/screenings/99999/")
    assert missing.status_code == 404
    assert missing.get_json()["detail"] == "Screening not found."

    upload = client.post(
        "/api/v1/screenings/99999/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 404

    analyze = client.post("/api/v1/screenings/99999/analyze/")
    assert analyze.status_code == 404

    assessment = client.post(
        "/api/v1/screenings/99999/assessment/",
        json={"result": "normal"},
    )
    assert assessment.status_code == 404


def test_missing_image(client):
    response = client.get("/api/v1/images/99999/")
    assert response.status_code == 404
    assert response.get_json()["detail"] == "Image not found."

    file_response = client.get("/api/v1/images/99999/file")
    assert file_response.status_code == 404


def test_invalid_request(client, facility):
    bad_code = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "x"},
    )
    assert bad_code.status_code == 422
    assert "detail" in bad_code.get_json()

    missing_fields = client.post("/api/v1/facilities/", json={"name": ""})
    assert missing_fields.status_code == 422
    assert "detail" in missing_fields.get_json()

    created = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000020"},
    )
    assert created.status_code == 201
    screening_id = created.get_json()["id"]

    empty_update = client.patch(f"/api/v1/screenings/{screening_id}/", json={})
    assert empty_update.status_code == 400
    assert empty_update.get_json()["detail"] == "No fields provided for update."


def test_ai_invalid_response(client, facility, app):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000021"},
    ).get_json()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"prediction": "abnormal"}

    upload = client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    job_id = upload.get_json()["analysis_job"]["id"]

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        with app.app_context():
            from app.services.queue_service import process_next

            assert process_next() is True

    job = client.get(f"/api/v1/analysis-jobs/{job_id}/").get_json()
    assert job["status"] == "failed"
    assert job["error_detail"] == "AI service returned an incomplete response."


def test_health_database_error(client):
    with patch(
        "app.routes.health_routes.db.session.execute",
        side_effect=RuntimeError("db down"),
    ):
        response = client.get("/api/v1/health/")

    assert response.status_code == 503
    assert response.get_json() == {"status": "degraded", "database": "disconnected"}


def test_invalid_assessment(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000022"},
    ).get_json()

    empty = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": ""},
    )
    assert empty.status_code == 422
    assert "detail" in empty.get_json()

    created = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "normal", "notes": "ok"},
    )
    assert created.status_code == 201

    duplicate = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "abnormal"},
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["detail"] == "Assessment already exists for this screening."

    missing = client.get(f"/api/v1/screenings/{screening['id'] + 1000}/assessment/")
    assert missing.status_code == 404


def test_api_index(client):
    expected = {
        "name": "VISCAN API",
        "version": "v1",
        "health": "/api/v1/health/",
        "docs": "/api/v1/docs",
        "openapi": "/api/v1/openapi.json",
    }
    for path in ("/", "/api/v1/"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.get_json() == expected

    redirected = client.get("/api/v1")
    assert redirected.status_code == 308
    assert redirected.headers["Location"].endswith("/api/v1/")


def test_openapi_available(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.get_json()["info"]["title"] == "VISCAN API"

    docs = client.get("/api/v1/docs/")
    assert docs.status_code == 308
    assert docs.headers["Location"].endswith("/api/v1/docs")
