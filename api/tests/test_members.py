"""Tests module 2 — nécessitent PostgreSQL (docker compose up -d)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def _db_available() -> bool:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _grant_role(email: str, role: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT u.id, r.id
                FROM users u
                CROSS JOIN roles r
                WHERE u.email = :email
                  AND r.code = :role
                  AND NOT EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = u.id
                      AND ur.role_id = r.id
                      AND ur.community_id IS NULL
                  )
                """
            ),
            {"email": email, "role": role},
        )
    await engine.dispose()


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def require_db() -> None:
    if not await _db_available():
        pytest.skip("PostgreSQL indisponible — lancez: docker compose up -d")


async def _register(client: AsyncClient, prefix: str) -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secret123!"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "preferred_language": "fr"},
    )
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return email, login.json()["access_token"]


async def test_directory_profile_and_pii_hidden(client: AsyncClient, require_db: None) -> None:
    email, token = await _register(client, "mem")
    headers = {"Authorization": f"Bearer {token}"}
    handle = f"dev{uuid.uuid4().hex[:6]}"

    editor_email, editor_token = await _register(client, "ed")
    await _grant_role(editor_email, "editor")
    editor_login = await client.post(
        "/api/v1/auth/login",
        json={"email": editor_email, "password": "Secret123!"},
    )
    editor_headers = {"Authorization": f"Bearer {editor_login.json()['access_token']}"}
    tech = await client.post(
        "/api/v1/admin/technologies",
        headers=editor_headers,
        json={
            "slug": f"py{uuid.uuid4().hex[:4]}",
            "name": f"Python {uuid.uuid4().hex[:4]}",
            "category": "langage",
        },
    )
    assert tech.status_code == 201, tech.text
    slug = tech.json()["slug"]

    created = await client.put(
        "/api/v1/members/me",
        headers=headers,
        json={
            "handle": handle,
            "display_name": "Awa Dev",
            "title": "Développeuse",
            "city": "Lome",
            "country_code": "TG",
            "member_status": "professional",
            "visibility": "public",
            "listed_in_directory": True,
            "show_location": True,
            "show_links": False,
            "github_url": "https://github.com/awa",
            "technologies": [{"slug": slug, "level": 4}],
        },
    )
    assert created.status_code == 200, created.text
    assert "email" not in created.json()

    pii = await client.put(
        "/api/v1/members/me/pii",
        headers=headers,
        json={"first_name": "Awa", "last_name": "K", "phone": "+22890000000"},
    )
    assert pii.status_code == 200, pii.text

    public = await client.get(f"/api/v1/directory/{handle}")
    assert public.status_code == 200, public.text
    body = public.json()
    assert body["city"] == "Lome"
    assert body["github_url"] is None
    assert "first_name" not in body
    assert "email" not in body
    assert "phone" not in body

    listing = await client.get("/api/v1/directory", params={"q": handle, "technology": slug, "city": "Lome"})
    assert listing.status_code == 200, listing.text
    assert any(item["handle"] == handle for item in listing.json()["items"])

    dash = await client.get("/api/v1/members/me/dashboard", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["events"] == []


async def test_hidden_profile_absent_and_export(client: AsyncClient, require_db: None) -> None:
    email, token = await _register(client, "hide")
    headers = {"Authorization": f"Bearer {token}"}
    handle = f"hid{uuid.uuid4().hex[:6]}"
    me = await client.get("/api/v1/users/me", headers=headers)
    user_id = me.json()["id"]
    await client.put(
        "/api/v1/members/me",
        headers=headers,
        json={
            "handle": handle,
            "display_name": "Cache",
            "visibility": "public",
            "listed_in_directory": True,
        },
    )

    denied = await client.get("/api/v1/admin/members/export", headers=headers)
    assert denied.status_code == 403

    admin_email, _ = await _register(client, "adm")
    await _grant_role(admin_email, "admin")
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "Secret123!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    hidden = await client.post(
        f"/api/v1/admin/members/{user_id}/visibility",
        headers=admin_headers,
        json={"hidden": True},
    )
    assert hidden.status_code == 200, hidden.text
    missing = await client.get(f"/api/v1/directory/{handle}")
    assert missing.status_code == 404

    exported = await client.get("/api/v1/admin/members/export", headers=admin_headers)
    assert exported.status_code == 200
    assert "handle" in exported.text
    assert handle in exported.text


async def test_member_contact_honeypot(client: AsyncClient, require_db: None) -> None:
    _, token = await _register(client, "box")
    headers = {"Authorization": f"Bearer {token}"}
    handle = f"box{uuid.uuid4().hex[:6]}"
    await client.put(
        "/api/v1/members/me",
        headers=headers,
        json={
            "handle": handle,
            "display_name": "Boite",
            "visibility": "public",
            "listed_in_directory": True,
            "allow_contact": True,
        },
    )
    spam = await client.post(
        f"/api/v1/directory/{handle}/contact",
        json={"name": "Bot", "email": "b@x.com", "message": "hi", "website": "http://spam"},
    )
    assert spam.status_code == 400
    ok = await client.post(
        f"/api/v1/directory/{handle}/contact",
        json={"name": "Ada", "email": "ada@example.com", "message": "Bonjour"},
    )
    assert ok.status_code == 201, ok.text
