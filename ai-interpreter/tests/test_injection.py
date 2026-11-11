"""Request fields are data. They are not executed, and they are not SQL."""

import io

import pytest

from app.models import ViaImage
from tests.test_api import cervix_image, upload

pytestmark = pytest.mark.security


@pytest.fixture
def client(tmp_path):
    from app import create_app

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_DIR": tmp_path,
        "INTERPRETER_MODE": "heuristic",
        "API_KEY": "",
    })
    return app.test_client()


def test_lookup_treats_a_sql_fragment_as_a_patient_id(client):
    upload(client, cervix_image(False), patient_external_id="CLINIC-1", age="34", hiv_status="negative")
    upload(client, cervix_image(True), patient_external_id="CLINIC-2", age="41", hiv_status="negative")
    attack = client.get("/api/v1/patients/lookup", query_string={"external_id": "' OR '1'='1"})
    assert attack.status_code == 200
    assert attack.json["found"] is False
    assert attack.json["screenings_count"] == 0
    real = client.get("/api/v1/patients/lookup", query_string={"external_id": "CLINIC-1"})
    assert real.json["found"] is True
    assert real.json["external_id"] == "CLINIC-1"


def test_upload_name_is_replaced_by_the_content_hash(client):
    response = client.post(
        "/api/v1/interpret",
        data={"image": (io.BytesIO(cervix_image(True)), "../../etc/passwd.jpg"), "patient_external_id": "CLINIC-3"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    with client.application.app_context():
        stored = ViaImage.query.order_by(ViaImage.id.desc()).first()
        assert stored.filename == f"{stored.sha256}.jpg"
        assert ".." not in stored.filename
        assert "passwd" not in stored.filename


def test_shell_metacharacters_in_age_are_rejected(client):
    response = client.post(
        "/api/v1/interpret",
        data={
            "image": (io.BytesIO(cervix_image(False)), "via.jpg"),
            "age": "34; rm -rf /",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_report_escapes_annotation_notes(client):
    created = upload(client, cervix_image(True), patient_external_id="CLINIC-4")
    interp_id = created.json["interpretation_id"]
    notes = "<script>alert(1)</script>"
    saved = client.post(
        f"/api/v1/interpretations/{interp_id}/annotations",
        json={"clinician_id": "nurse-1", "via_result": "VIA_NEGATIVE", "lesion_clock_positions": [], "notes": notes},
    )
    assert saved.status_code == 201
    assert saved.json["notes"] == notes
    page = client.get(f"/api/v1/interpretations/{interp_id}/report")
    assert page.status_code == 200
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in page.data
