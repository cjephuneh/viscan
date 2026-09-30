import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test the root welcome endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["port"] == 9090
    assert data["status"] == "online"


@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient):
    """Test root health endpoint /health."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["port"] == 9090
    assert "database_connected" in data
    assert "anam_configured" in data


@pytest.mark.asyncio
async def test_api_v1_health_check(client: AsyncClient):
    """Test v1 health endpoint /api/v1/health."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "timestamp" in data
