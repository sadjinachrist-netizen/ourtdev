"""Tests module 4 — nécessitent PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

API = "/api/v1"
PASSWORD = "motdepasse1"


async def _register(client: AsyncClient) -> dict[str, str]:
    email = f"u{uuid.uuid4().hex[:10]}@test.tdev"
    created = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "preferred_language": "fr"},
    )
    assert created.status_code == 201, created.text
    logged = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert logged.status_code == 200, logged.text
    return {"user_id": created.json()["id"], "access": logged.json()["access_token"]}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _grant(user_id: str, role: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id)
                SELECT CAST(:uid AS uuid), r.id
                FROM roles r
                WHERE r.code = :code
                  AND NOT EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = CAST(:uid AS uuid)
                      AND ur.role_id = r.id
                      AND ur.community_id IS NULL
                  )
                """
            ),
            {"uid": user_id, "code": role},
        )
        await session.commit()


async def _free_years() -> tuple[int, int]:
    async with AsyncSessionLocal() as session:
        current = (
            await session.execute(text("SELECT COALESCE(MAX(year), 2019) FROM festival_editions"))
        ).scalar_one()
    base = int(current) + 1
    return base, base + 1


async def test_festival_editions_announcements_and_redirects(client: AsyncClient) -> None:
    status = await client.get(f"{API}/festival/status")
    assert status.status_code == 200
    assert status.json()["status"] == "ready"

    admin = await _register(client)
    member = await _register(client)
    await _grant(admin["user_id"], "admin")
    admin_headers = _auth(admin["access"])
    member_headers = _auth(member["access"])
    current_year, archive_year = await _free_years()
    old_path = f"/billets-{current_year}"
    published_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    denied = await client.post(
        f"{API}/admin/festival/editions",
        headers=member_headers,
        json={
            "year": current_year,
            "city": "Lomé",
            "is_current": True,
            "target_url": old_path,
            "translations": [{"language_code": "fr", "theme": "Thème interdit"}],
        },
    )
    assert denied.status_code == 403

    created = await client.post(
        f"{API}/admin/festival/editions",
        headers=admin_headers,
        json={
            "year": current_year,
            "starts_on": f"{current_year}-11-20",
            "ends_on": f"{current_year}-11-22",
            "city": "Lomé",
            "venue": "Campus",
            "is_current": True,
            "target_url": old_path,
            "translations": [
                {
                    "language_code": "fr",
                    "theme": f"Thème {current_year}",
                    "summary": "Résumé",
                    "description": "Description",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    assert (await client.get(f"{API}/festival/{current_year}")).status_code == 404

    published = await client.post(
        f"{API}/admin/festival/editions/{current_year}/publish",
        headers=admin_headers,
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["theme"] == f"Thème {current_year}"

    page = await client.get(f"{API}/festival?lang=fr")
    assert page.status_code == 200
    assert page.json()["current"]["year"] == current_year
    current = await client.get(f"{API}/festival/current")
    assert current.status_code == 200
    assert current.json()["year"] == current_year

    figured = await client.post(
        f"{API}/admin/festival/editions/{current_year}/figures",
        headers=admin_headers,
        json={"code": "visiteurs", "value": 800, "suffix": "+", "label_fr": "Visiteurs", "label_en": "Visitors"},
    )
    assert figured.status_code == 201, figured.text
    assert figured.json()["figures"][0]["label"] == "Visiteurs"
    detail_en = await client.get(f"{API}/festival/{current_year}?lang=en")
    assert detail_en.json()["figures"][0]["label"] == "Visitors"

    archived = await client.post(
        f"{API}/admin/festival/editions",
        headers=admin_headers,
        json={
            "year": archive_year,
            "starts_on": f"{archive_year}-11-01",
            "ends_on": f"{archive_year}-11-02",
            "city": "Lomé",
            "status": "published",
            "published_at": published_at,
            "is_current": False,
            "target_url": f"https://archive.example/{archive_year}",
            "translations": [{"language_code": "fr", "theme": f"Archive {archive_year}"}],
        },
    )
    assert archived.status_code == 201, archived.text
    archive_page = await client.get(f"{API}/festival")
    assert archive_page.json()["current"]["year"] == current_year
    assert any(item["year"] == archive_year for item in archive_page.json()["archive"])

    switched = await client.patch(
        f"{API}/admin/festival/editions/{archive_year}",
        headers=admin_headers,
        json={"is_current": True},
    )
    assert switched.status_code == 200, switched.text
    assert (await client.get(f"{API}/festival/current")).json()["year"] == archive_year
    restored = await client.patch(
        f"{API}/admin/festival/editions/{current_year}",
        headers=admin_headers,
        json={"is_current": True},
    )
    assert restored.status_code == 200

    moved = await client.patch(
        f"{API}/admin/festival/editions/{current_year}",
        headers=admin_headers,
        json={"target_url": f"https://festival.example/{current_year}"},
    )
    assert moved.status_code == 200
    assert moved.json()["target_url"] == f"https://festival.example/{current_year}"

    jump = await client.get(f"{API}/festival/{current_year}/go")
    assert jump.status_code == 301
    assert jump.headers["location"] == f"https://festival.example/{current_year}"
    old = await client.get("/api/v1/redirects/resolve", params={"path": old_path})
    assert old.status_code == 301
    assert old.headers["location"] == f"https://festival.example/{current_year}"

    redirects = await client.get(f"{API}/admin/redirects", headers=admin_headers)
    assert redirects.status_code == 200
    by_path = {row["source_path"]: row for row in redirects.json()}
    assert by_path[f"/festival/{current_year}"]["hit_count"] >= 1
    assert by_path[old_path]["hit_count"] >= 1
    member_redirects = await client.get(f"{API}/admin/redirects", headers=member_headers)
    assert member_redirects.status_code == 403

    now = datetime.now(timezone.utc)
    announcement = await client.post(
        f"{API}/admin/festival/announcements",
        headers=admin_headers,
        json={
            "edition_year": current_year,
            "kind": "registration",
            "cta_url": "https://festival.example/inscription",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=5)).isoformat(),
            "translations": [{"language_code": "fr", "message": f"Inscriptions {current_year}", "cta_label": "Je m'inscris"}],
        },
    )
    assert announcement.status_code == 201, announcement.text
    banner = await client.get(f"{API}/festival/announcements")
    assert any(item["message"] == f"Inscriptions {current_year}" for item in banner.json())
    home = await client.get(f"{API}/home")
    assert any(item["kind"] == "registration" and item["message"] == f"Inscriptions {current_year}" for item in home.json()["announcements"])

    hidden = await client.patch(
        f"{API}/admin/festival/announcements/{announcement.json()['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert hidden.status_code == 200
    banner_after = await client.get(f"{API}/festival/announcements")
    assert all(item["message"] != f"Inscriptions {current_year}" for item in banner_after.json())
