import io
import threading
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.errors import APIError
from app.extensions import db
from app.models import AnalysisJob, Facility, Screening
from app.services.analysis_worker import start_analysis_worker, stop_analysis_worker
from app.services.queue_service import build_queue_view, process_next
from app.utils.time import utcnow


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
        return item.id


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(20, 120, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def _ai_payload() -> dict:
    return {
        "prediction": "normal",
        "confidence": 0.8,
        "model_version": "v1.0",
        "processing_time_ms": 10,
    }


def _screening(client, facility, patient_code):
    response = client.post(
        "/api/v1/screenings/",
        json={"facility_id": facility, "patient_code": patient_code},
    )
    assert response.status_code == 201
    return response.get_json()


def _upload(client, screening_id):
    response = client.post(
        f"/api/v1/screenings/{screening_id}/images/",
        data={"file": (io.BytesIO(_png_bytes()), "via.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    return response.get_json()


def _wait_until(predicate, timeout=5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_uploads_line_up_until_the_worker_reaches_them(client, facility):
    first = _screening(client, facility, "VIA-000101")
    second = _screening(client, facility, "VIA-000102")
    third = _screening(client, facility, "VIA-000103")
    _upload(client, first["id"])
    _upload(client, second["id"])
    _upload(client, third["id"])

    queue = client.get("/api/v1/analysis-queue/").get_json()
    assert queue["processing_count"] == 0
    assert queue["queued_count"] == 3
    assert queue["processing"] is None
    assert [job["ahead"] for job in queue["queued"]] == [0, 1, 2]
    assert [job["position"] for job in queue["queued"]] == [1, 2, 3]
    assert [job["screening_id"] for job in queue["queued"]] == [
        first["id"],
        second["id"],
        third["id"],
    ]


def test_only_the_claimed_image_is_sent_to_the_model(client, app, facility):
    first = _upload(client, _screening(client, facility, "VIA-000111")["id"])
    second = _upload(client, _screening(client, facility, "VIA-000112")["id"])
    seen = []

    def fake(image_url, image_id):
        seen.append(image_id)
        if image_id == first["id"]:
            queue = build_queue_view()
            assert queue["processing"]["via_image_id"] == first["id"]
            assert queue["processing"]["ahead"] == 0
            assert queue["queued_count"] == 1
            assert queue["queued"][0]["via_image_id"] == second["id"]
            assert queue["queued"][0]["ahead"] == 1
        return _ai_payload()

    with patch("app.services.ai_service.analyze_image", side_effect=fake):
        with app.app_context():
            assert process_next() is True
            assert seen == [first["id"]]
            assert process_next() is True
            assert seen == [first["id"], second["id"]]
            assert process_next() is False

    finished = client.get("/api/v1/analysis-queue/").get_json()
    assert finished["processing_count"] == 0
    assert finished["queued_count"] == 0
    assert {job["status"] for job in finished["recently_finished"]} == {"completed"}
    assert client.get(f"/api/v1/screenings/{first['screening_id']}/").get_json()["status"] == "ANALYZED"


def test_a_failed_image_does_not_block_the_next_one(client, app, facility):
    first = _upload(client, _screening(client, facility, "VIA-000121")["id"])
    second = _upload(client, _screening(client, facility, "VIA-000122")["id"])

    def fake(image_url, image_id):
        if image_id == first["id"]:
            raise APIError("AI service is unavailable.", 503)
        return _ai_payload()

    with patch("app.services.ai_service.analyze_image", side_effect=fake):
        with app.app_context():
            assert process_next() is True
            assert process_next() is True

    failed = client.get(f"/api/v1/analysis-jobs/{first['analysis_job']['id']}/").get_json()
    completed = client.get(f"/api/v1/analysis-jobs/{second['analysis_job']['id']}/").get_json()
    assert failed["status"] == "failed"
    assert completed["status"] == "completed"
    assert completed["ai_result"]["prediction"] == "normal"

    retry = client.post(f"/api/v1/screenings/{first['screening_id']}/analyze/")
    assert retry.status_code == 202
    assert retry.get_json()["status"] == "queued"
    assert retry.get_json()["id"] != first["analysis_job"]["id"]


def test_upload_is_accepted_while_another_image_is_processing(client, app, facility):
    gate = threading.Event()
    started = []

    def fake(image_url, image_id):
        started.append(image_id)
        assert gate.wait(5)
        return _ai_payload()

    first_screening = _screening(client, facility, "VIA-000131")
    second_screening = _screening(client, facility, "VIA-000132")
    try:
        with patch("app.services.ai_service.analyze_image", side_effect=fake):
            start_analysis_worker(app)
            first = _upload(client, first_screening["id"])
            assert _wait_until(lambda: started == [first["id"]])

            second = _upload(client, second_screening["id"])
            assert second["analysis_job"]["status"] == "queued"
            assert started == [first["id"]]

            queue = client.get("/api/v1/analysis-queue/").get_json()
            assert queue["processing_count"] == 1
            assert queue["queued_count"] == 1
            assert queue["processing"]["via_image_id"] == first["id"]
            assert queue["processing"]["status"] == "processing"
            assert queue["queued"][0]["via_image_id"] == second["id"]
            assert queue["queued"][0]["position"] == 2
            assert queue["queued"][0]["ahead"] == 1
            assert (
                client.get(f"/api/v1/screenings/{first_screening['id']}/").get_json()["status"]
                == "ANALYZING"
            )
            assert (
                client.get(f"/api/v1/screenings/{second_screening['id']}/").get_json()["status"]
                == "QUEUED"
            )

            gate.set()
            assert _wait_until(
                lambda: client.get("/api/v1/analysis-queue/").get_json()["queued_count"] == 0
                and client.get("/api/v1/analysis-queue/").get_json()["processing_count"] == 0
            )
    finally:
        gate.set()
        stop_analysis_worker(app)

    assert started == [first["id"], second["id"]]
    assert client.get(f"/api/v1/screenings/{second_screening['id']}/").get_json()["status"] == "ANALYZED"


def test_database_allows_only_one_processing_job(client, app, facility):
    _upload(client, _screening(client, facility, "VIA-000141")["id"])
    _upload(client, _screening(client, facility, "VIA-000142")["id"])

    with app.app_context():
        jobs = AnalysisJob.query.order_by(AnalysisJob.id).all()
        jobs[0].status = "processing"
        jobs[0].started_at = utcnow()
        db.session.commit()
        jobs[1].status = "processing"
        jobs[1].started_at = utcnow()
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_stale_processing_job_is_dropped_after_the_last_attempt(client, app, facility):
    uploaded = _upload(client, _screening(client, facility, "VIA-000151")["id"])

    with app.app_context():
        job = db.session.get(AnalysisJob, uploaded["analysis_job"]["id"])
        job.status = "processing"
        job.attempts = 2
        job.started_at = utcnow() - timedelta(seconds=500)
        screening = db.session.get(Screening, uploaded["screening_id"])
        screening.status = "ANALYZING"
        db.session.commit()
        assert process_next() is False
        db.session.refresh(job)
        status = job.status
        detail = job.error_detail
        job_id = job.id

    assert status == "failed"
    assert detail == "Analysis did not finish and was removed from the queue."
    stored = client.get(f"/api/v1/analysis-jobs/{job_id}/").get_json()
    assert stored["status"] == "failed"
    assert client.get(f"/api/v1/screenings/{uploaded['screening_id']}/").get_json()["status"] == (
        "ANALYSIS_FAILED"
    )


def test_missing_analysis_job(client):
    response = client.get("/api/v1/analysis-jobs/99999/")
    assert response.status_code == 404
    assert response.get_json()["detail"] == "Analysis job not found."
