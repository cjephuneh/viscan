from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_video_status_endpoint(client: AsyncClient, sample_hsil_payload: dict):
    """Test retrieving video URL and status for an existing report."""
    # Ensure report exists
    post_res = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert post_res.status_code in [201, 409]

    scan_id = sample_hsil_payload["scan_id"]
    response = await client.get(f"/api/v1/reports/{scan_id}/video")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] in ["pending", "running", "completed", "uninitiated"]
    assert "player_url" in data
    assert data["player_url"] == f"/player/{data['report_id']}"
    assert "instructions" in data


@pytest.mark.asyncio
async def test_trigger_report_video_render(client: AsyncClient, sample_hsil_payload: dict):
    """Test explicitly requesting video render generation with mock to ensure CI stability."""
    post_res = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert post_res.status_code in [201, 409]

    scan_id = sample_hsil_payload["scan_id"]

    with patch("app.api.v1.endpoints.reports.anam_service.create_avatar_video", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "id": "avv_test_job_999",
            "status": "running",
            "content": {"available": False},
            "durationSeconds": None,
        }
        response = await client.post(f"/api/v1/reports/{scan_id}/video")
        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == "avv_test_job_999"
        assert data["status"] == "running"
        assert "player_url" in data


@pytest.mark.asyncio
async def test_player_html_page_rendering(client: AsyncClient, sample_hsil_payload: dict):
    """Test the hosted HTML5 video player page loads correctly."""
    post_res = await client.post("/api/v1/reports", json=sample_hsil_payload)
    assert post_res.status_code in [201, 409]

    scan_id = sample_hsil_payload["scan_id"]
    response = await client.get(f"/player/{scan_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    html = response.text
    # Verify core clinical player elements are present
    assert "ViScan Clinician Avatar Video" in html
    assert scan_id in html
    assert sample_hsil_payload["patient_id"] in html
    assert "Digital Clinician Avatar" in html
    assert "Cervical Assessment Details" in html
    assert "copyVideoUrl" in html
    assert "copyEmbedCode" in html


@pytest.mark.asyncio
async def test_player_page_nonexistent_report_404(client: AsyncClient):
    """Test requesting a player page for an invalid ID returns 404."""
    response = await client.get("/player/INVALID-NONEXISTENT-SCAN-999")
    assert response.status_code == 404
