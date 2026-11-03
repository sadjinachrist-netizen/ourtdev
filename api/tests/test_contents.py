"""Tests module 1 — nécessitent PostgreSQL (docker compose up -d)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.shared.rate_limit import contact_rate_limiter


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


async def _grant_editor(email: str) -> None:
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
                  AND r.code = 'editor'
                  AND NOT EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = u.id
                      AND ur.role_id = r.id
                      AND ur.community_id IS NULL
                  )
                """
            ),
            {"email": email},
        )
    await engine.dispose()


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def require_db() -> None:
    if not await _db_available():
        pytest.skip("PostgreSQL indisponible — lancez: docker compose up -d")


@pytest.fixture
async def editor_token(client: AsyncClient, require_db: None) -> str:
    email = f"editor_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secret123!"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "preferred_language": "fr"},
    )
    await _grant_editor(email)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def test_home_ok(client: AsyncClient, require_db: None) -> None:
    resp = await client.get("/api/v1/home?lang=fr")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "key_figures" in data
    assert "partners" in data
    assert "upcoming_events" in data
    assert "latest_articles" in data
    assert isinstance(data["key_figures"], list)


async def test_publish_page_then_get(
    client: AsyncClient, require_db: None, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    pages = await client.get("/api/v1/admin/pages", headers=headers)
    assert pages.status_code == 200, pages.text
    about = next(p for p in pages.json() if p["slug"] == "a-propos")
    pub = await client.post(
        f"/api/v1/admin/pages/{about['id']}/publish",
        headers=headers,
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "published"

    public = await client.get("/api/v1/pages/a-propos?lang=fr")
    assert public.status_code == 200, public.text
    assert public.json()["title"] == "À propos"
    assert public.json()["language"] == "fr"


async def test_contact_and_honeypot(client: AsyncClient, require_db: None) -> None:
    contact_rate_limiter._hits.clear()
    ok = await client.post(
        "/api/v1/contact",
        json={
            "name": "Test",
            "email": f"c_{uuid.uuid4().hex[:6]}@example.com",
            "subject": "Hello",
            "message": "Message de test",
        },
    )
    assert ok.status_code == 201, ok.text

    spam = await client.post(
        "/api/v1/contact",
        json={
            "name": "Bot",
            "email": "bot@example.com",
            "message": "spam",
            "website": "http://spam.test",
        },
    )
    assert spam.status_code == 400


async def test_contact_rate_limit(client: AsyncClient, require_db: None) -> None:
    contact_rate_limiter._hits.clear()
    # Force low limit for this key by filling bucket
    ip_key = "contact:testclient"
    for _ in range(5):
        contact_rate_limiter.check(ip_key)
    # Monkey: use same IP — TestClient may use different host; fill via override
    # Directly check limiter then call endpoint with mocked hits for "contact:test"
    # Instead: call endpoint 6 times quickly after clearing and patching client_ip effect
    contact_rate_limiter._hits.clear()
    payloads = [
        {
            "name": "R",
            "email": f"r{i}_{uuid.uuid4().hex[:4]}@example.com",
            "message": "msg",
        }
        for i in range(6)
    ]
    statuses = []
    for payload in payloads:
        r = await client.post("/api/v1/contact", json=payload)
        statuses.append(r.status_code)
    assert 201 in statuses
    assert 429 in statuses


async def test_articles_list(client: AsyncClient, require_db: None) -> None:
    resp = await client.get("/api/v1/articles?lang=fr")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_create_article_as_editor(
    client: AsyncClient, require_db: None, editor_token: str
) -> None:
    headers = {"Authorization": f"Bearer {editor_token}"}
    slug = f"news-{uuid.uuid4().hex[:6]}"
    created = await client.post(
        "/api/v1/admin/articles",
        headers=headers,
        json={
            "slug": slug,
            "status": "published",
            "published_at": "2020-01-01T00:00:00Z",
            "translations": [
                {
                    "language_code": "fr",
                    "title": "Actu test",
                    "summary": "extrait",
                    "body": "contenu",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    public = await client.get(f"/api/v1/articles/{slug}?lang=fr")
    assert public.status_code == 200
    assert public.json()["title"] == "Actu test"
