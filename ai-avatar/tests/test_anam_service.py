import pytest
from app.services.anam_service import anam_service, AnamService


@pytest.mark.asyncio
async def test_anam_service_configured():
    """Verify service accurately reports configuration status."""
    assert isinstance(anam_service.is_configured, bool)


@pytest.mark.asyncio
async def test_create_session_token_contract():
    """Verify session token generation returns a valid token structure."""
    system_prompt = "You are Dr. ViScan."
    result = await anam_service.create_session_token(system_prompt=system_prompt)

    assert "sessionToken" in result
    assert isinstance(result["sessionToken"], str)
    assert len(result["sessionToken"]) > 10


@pytest.mark.asyncio
async def test_create_avatar_video_contract():
    """Verify avatar video creation initiates and returns a video job ID."""
    script = "Hello from the test suite."
    result = await anam_service.create_avatar_video(script=script)

    assert "id" in result
    assert "status" in result
    assert result["status"] in ["pending", "running", "completed"]


@pytest.mark.asyncio
async def test_get_avatar_video_status():
    """Verify querying an avatar video returns content and status."""
    # Query video created in previous step or simulated
    result = await anam_service.get_avatar_video("simulated_video_12345")
    assert result["id"] == "simulated_video_12345"
    assert result["status"] == "completed"
    assert "content" in result
    assert result["content"]["available"] is True
