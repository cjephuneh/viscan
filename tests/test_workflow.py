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
        json={"facility_id": facility, "patient_code": "VIA-000010"},
    ).get_json()

    upload = client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    image = upload.get_json()
    assert image["media_type"] == "image/png"

    status = client.get(f"/api/v1/screenings/{screening['id']}/").get_json()["status"]
    assert status == "IMAGE_UPLOADED"

    ai_payload = {
        "prediction": "abnormal",
        "confidence": 0.91,
        "model_version": "v1.0",
        "processing_time_ms": 842,
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ai_payload

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        analyze = client.post(f"/api/v1/screenings/{screening['id']}/analyze/")

    assert analyze.status_code == 201
    result = analyze.get_json()
    assert result["prediction"] == "abnormal"
    assert result["confidence"] == 0.91

    assessment = client.post(
        f"/api/v1/screenings/{screening['id']}/assessment/",
        json={"result": "abnormal", "notes": "Clinician confirmed"},
    )
    assert assessment.status_code == 201
    assert assessment.get_json()["result"] == "abnormal"

    final = client.get(f"/api/v1/screenings/{screening['id']}/")
    assert final.status_code == 200
    assert final.get_json()["status"] == "REVIEWED"
    assert final.get_json()["assessment"]["result"] == "abnormal"


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


def test_ai_unavailable(client, facility):
    screening = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": "VIA-000013"},
    ).get_json()
    client.post(
        f"/api/v1/screenings/{screening['id']}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )

    import httpx

    with patch("app.services.ai_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError(
            "down"
        )
        response = client.post(f"/api/v1/screenings/{screening['id']}/analyze/")

    assert response.status_code == 503
    assert response.get_json()["detail"] == "AI service is unavailable."


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

    voice = client.post(
        "/api/v1/voice/synthesize/",
        json={"text": "Hello", "language": "en"},
    )
    assert voice.status_code == 200
    assert voice.get_json()["provider"] == "stub"


def test_openapi_available(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert response.get_json()["info"]["title"] == "VISCAN API"
