"""Tests auth — nécessitent PostgreSQL (docker compose up -d)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _db_available() -> bool:
    from app.core.config import get_settings

    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def require_db() -> None:
    if not await _db_available():
        pytest.skip("PostgreSQL indisponible — lancez: docker compose up -d")


async def test_register_login_refresh(client: AsyncClient, require_db: None) -> None:
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secret123!"

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "preferred_language": "fr"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["email"] == email
    assert "password_hash" not in body

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email
    assert "profile.edit_own" in me.json()["permissions"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    assert "access_token" in refreshed.json()


async def test_login_wrong_password(client: AsyncClient, require_db: None) -> None:
    email = f"bad_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Secret123!", "preferred_language": "fr"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_me_unauthorized(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
