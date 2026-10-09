from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "env" in data


async def test_auth_status_ready(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
