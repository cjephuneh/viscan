import os

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_report_success(client: AsyncClient, sample_hsil_payload: dict):
    """Test successful creation of a cervical avatar report."""
    response = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert response.status_code == 201
    data = response.json()

    assert data["scan_id"] == sample_hsil_payload["scan_id"]
    assert data["patient_id"] == sample_hsil_payload["patient_id"]
    assert data["screening_result"] == sample_hsil_payload["screening_result"]
    assert data["confidence_score"] == 0.94
    assert "generated_script" in data
    assert "player_url" in data
    assert data["player_url"].startswith("/player/")
    assert data["status"] == "READY"


@pytest.mark.asyncio
async def test_create_duplicate_scan_id_conflict(client: AsyncClient, sample_hsil_payload: dict):
    """Test that submitting an existing scan_id returns a 409 Conflict."""
    # First creation
    res1 = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert res1.status_code in [201, 409]

    # Duplicate creation
    res2 = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_create_report_validation_error(client: AsyncClient):
    """Test that missing required fields produces a 422 validation error."""
    invalid_payload = {
        "scan_id": "SCAN-INCOMPLETE",
        # Missing patient_id, screening_result, recommendations
    }
    response = await client.post("/api/v1/reports", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_report_by_id_and_scan_id(client: AsyncClient, sample_normal_payload: dict):
    """Test fetching a report by primary UUID and by scan_id."""
    res_post = await client.post("/api/v1/reports", json=sample_normal_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    report_id = created["id"]
    scan_id = created["scan_id"]

    # 1. Fetch by UUID
    res_uuid = await client.get(f"/api/v1/reports/{report_id}")
    assert res_uuid.status_code == 200
    assert res_uuid.json()["id"] == report_id

    # 2. Fetch by scan_id
    res_scan = await client.get(f"/api/v1/reports/{scan_id}")
    assert res_scan.status_code == 200
    assert res_scan.json()["scan_id"] == scan_id


@pytest.mark.asyncio
async def test_get_nonexistent_report_404(client: AsyncClient):
    """Test requesting a non-existent report returns 404."""
    response = await client.get("/api/v1/reports/NON-EXISTENT-ID-999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_reports_and_filtering(client: AsyncClient, sample_hsil_payload: dict):
    """Test querying report collection and filtering by patient_id."""
    response = await client.get("/api/v1/reports", params={"patient_id": sample_hsil_payload["patient_id"]})
    assert response.status_code == 200
    reports = response.json()
    assert isinstance(reports, list)
    for r in reports:
        assert r["patient_id"] == sample_hsil_payload["patient_id"]


@pytest.mark.skipif(
    os.getenv("ANAM_LIVE_TESTS") != "1",
    reason="live Anam API test; set ANAM_LIVE_TESTS=1 with a real ANAM_API_KEY to run",
)
@pytest.mark.asyncio
async def test_generate_session_token(client: AsyncClient, sample_hsil_payload: dict):
    """Test generating a fresh WebRTC session token for an existing report."""
    scan_id = sample_hsil_payload["scan_id"]
    response = await client.post(f"/api/v1/reports/{scan_id}/session")
    assert response.status_code == 200
    data = response.json()

    assert "session_token" in data
    assert data["expires_in_seconds"] == 3600
    assert "system_prompt" in data
    assert "generated_script" in data


@pytest.mark.asyncio
async def test_delete_report(client: AsyncClient, sample_normal_payload: dict):
    """Test deleting a report and confirming 404 on subsequent fetch."""
    scan_id = sample_normal_payload["scan_id"]

    # Delete
    del_res = await client.delete(f"/api/v1/reports/{scan_id}")
    assert del_res.status_code == 204

    # Confirm deletion
    get_res = await client.get(f"/api/v1/reports/{scan_id}")
    assert get_res.status_code == 404
