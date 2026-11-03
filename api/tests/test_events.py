"""Tests module 3 — nécessitent PostgreSQL."""

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
    return {"email": email, "user_id": created.json()["id"], "access": logged.json()["access_token"]}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _grant(user_id: str, role: str, community_id: int | None = None) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id, community_id)
                SELECT CAST(:uid AS uuid), r.id, :community_id
                FROM roles r
                WHERE r.code = :code
                  AND NOT EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = CAST(:uid AS uuid)
                      AND ur.role_id = r.id
                      AND COALESCE(ur.community_id, 0) = COALESCE(:community_id, 0)
                  )
                """
            ),
            {"uid": user_id, "code": role, "community_id": community_id},
        )
        await session.commit()


async def _community(name: str) -> int:
    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text(
                """
                INSERT INTO communities (slug, name, kind, city, country_code)
                VALUES (:slug, :name, 'chapter', 'Lomé', 'TG')
                RETURNING id
                """
            ),
            {"slug": f"{name}-{uuid.uuid4().hex[:6]}", "name": name},
        )
        community_id = row.scalar_one()
        await session.commit()
        return community_id


def _event_body(slug: str, starts_at: datetime, **extra: object) -> dict:
    body = {
        "slug": slug,
        "type": "meetup",
        "format": "onsite",
        "starts_at": starts_at.isoformat(),
        "ends_at": (starts_at + timedelta(hours=2)).isoformat(),
        "city": "Lome",
        "venue": "Campus",
        "country_code": "TG",
        "registration_url": "https://example.com/inscription",
        "replay_url": "https://example.com/replay",
        "show_in_timeline": True,
        "translations": [
            {
                "language_code": "fr",
                "title": f"Meetup {slug}",
                "summary": "Résumé",
                "description": "Description",
            }
        ],
    }
    body.update(extra)
    return body


async def test_events_public_admin_and_registration(client: AsyncClient) -> None:
    status = await client.get(f"{API}/events/status")
    assert status.status_code == 200
    assert status.json()["status"] == "ready"

    editor = await _register(client)
    member = await _register(client)
    await _grant(editor["user_id"], "editor")
    editor_headers = _auth(editor["access"])
    member_headers = _auth(member["access"])
    suffix = uuid.uuid4().hex[:8]
    future = datetime(2027, 6, 15, 18, 0, tzinfo=timezone.utc)
    past = datetime(2020, 3, 1, 18, 0, tzinfo=timezone.utc)
    published_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    denied = await client.post(
        f"{API}/admin/events",
        headers=member_headers,
        json=_event_body(f"meetup-{suffix}", future),
    )
    assert denied.status_code == 403

    created = await client.post(
        f"{API}/admin/events",
        headers=editor_headers,
        json=_event_body(f"meetup-{suffix}", future, status="draft"),
    )
    assert created.status_code == 201, created.text
    event_id = created.json()["id"]
    hidden = await client.get(f"{API}/events/meetup-{suffix}")
    assert hidden.status_code == 404

    published = await client.post(f"{API}/admin/events/{event_id}/publish", headers=editor_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["resource_folder"]["slug"]
    assert published.json()["participants_count"] is None

    listing = await client.get(
        f"{API}/events",
        params={
            "when": "upcoming",
            "type": "meetup",
            "year": 2027,
            "city": "lome",
            "format": "onsite",
            "lang": "fr",
        },
    )
    assert listing.status_code == 200, listing.text
    assert any(item["slug"] == f"meetup-{suffix}" for item in listing.json()["items"])

    detail = await client.get(f"{API}/events/meetup-{suffix}?lang=fr")
    assert detail.status_code == 200
    assert detail.json()["title"] == f"Meetup meetup-{suffix}"
    assert detail.json()["replay_url"] == "https://example.com/replay"
    assert detail.json()["registration_url"]

    timeline = await client.get(f"{API}/events/timeline")
    assert any(item["slug"] == f"meetup-{suffix}" for item in timeline.json())

    off_timeline = await client.post(
        f"{API}/admin/events",
        headers=editor_headers,
        json=_event_body(
            f"hors-{suffix}",
            future,
            status="published",
            published_at=published_at,
            show_in_timeline=False,
        ),
    )
    assert off_timeline.status_code == 201, off_timeline.text
    timeline_slugs = {item["slug"] for item in (await client.get(f"{API}/events/timeline")).json()}
    assert f"hors-{suffix}" not in timeline_slugs

    ics = await client.get(f"{API}/events/meetup-{suffix}/calendar.ics")
    assert ics.status_code == 200
    assert "BEGIN:VCALENDAR" in ics.text
    assert f"Meetup meetup-{suffix}" in ics.text

    registered = await client.post(
        f"{API}/events/meetup-{suffix}/register",
        headers=member_headers,
        json={"role": "attendee"},
    )
    assert registered.status_code == 201, registered.text
    again = await client.post(
        f"{API}/events/meetup-{suffix}/register",
        headers=member_headers,
        json={"role": "attendee"},
    )
    assert again.status_code == 409

    speaker = await client.post(
        f"{API}/admin/speakers",
        headers=editor_headers,
        json={
            "full_name": f"Awa {suffix}",
            "organization": "TDEV",
            "translations": [{"language_code": "fr", "job_title": "Dev", "bio": "Bio"}],
        },
    )
    assert speaker.status_code == 201, speaker.text
    attached = await client.post(
        f"{API}/admin/events/{event_id}/speakers",
        headers=editor_headers,
        json={"speaker_id": speaker.json()["id"], "role": "speaker", "position": 1},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["speakers"][0]["full_name"] == f"Awa {suffix}"

    media = await client.post(
        f"{API}/admin/events/{event_id}/media",
        headers=editor_headers,
        json={"kind": "video", "url": "https://example.com/video", "position": 1},
    )
    assert media.status_code == 200, media.text
    assert media.json()["gallery"][0]["url"] == "https://example.com/video"

    partner = await client.post(
        f"{API}/admin/partners",
        headers=editor_headers,
        json={"slug": f"part-{suffix}", "name": f"Partenaire {suffix}"},
    )
    assert partner.status_code == 201, partner.text
    linked = await client.post(
        f"{API}/admin/events/{event_id}/partners",
        headers=editor_headers,
        json={"partner_id": partner.json()["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["partners"][0]["slug"] == f"part-{suffix}"

    stats = await client.patch(
        f"{API}/admin/events/{event_id}",
        headers=editor_headers,
        json={"show_stats": True, "participants_count": 40, "sessions_count": 3},
    )
    assert stats.status_code == 200, stats.text
    assert stats.json()["participants_count"] == 40
    assert stats.json()["sessions_count"] == 3

    past_event = await client.post(
        f"{API}/admin/events",
        headers=editor_headers,
        json=_event_body(
            f"passe-{suffix}",
            past,
            status="published",
            published_at=published_at,
            show_in_timeline=False,
        ),
    )
    assert past_event.status_code == 201, past_event.text
    past_list = await client.get(f"{API}/events", params={"when": "past", "year": 2020})
    assert any(item["slug"] == f"passe-{suffix}" for item in past_list.json()["items"])
    upcoming = await client.get(f"{API}/events", params={"when": "upcoming", "year": 2020})
    assert all(item["slug"] != f"passe-{suffix}" for item in upcoming.json()["items"])


async def test_lead_proposes_only_own_community(client: AsyncClient) -> None:
    own = await _community("propre")
    other = await _community("autre")
    lead = await _register(client)
    editor = await _register(client)
    await _grant(lead["user_id"], "lead", own)
    await _grant(editor["user_id"], "editor")
    lead_headers = _auth(lead["access"])
    suffix = uuid.uuid4().hex[:8]
    starts = datetime(2027, 9, 1, 10, 0, tzinfo=timezone.utc)

    outside = await client.post(
        f"{API}/admin/events",
        headers=lead_headers,
        json=_event_body(f"hors-commu-{suffix}", starts, community_id=other, status="draft"),
    )
    assert outside.status_code == 403

    proposed = await client.post(
        f"{API}/admin/events",
        headers=lead_headers,
        json=_event_body(f"lead-{suffix}", starts, community_id=own, status="in_review"),
    )
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "in_review"
    assert proposed.json()["community_id"] == own
    event_id = proposed.json()["id"]

    publish = await client.post(f"{API}/admin/events/{event_id}/publish", headers=lead_headers)
    assert publish.status_code == 403

    published = await client.post(
        f"{API}/admin/events/{event_id}/publish",
        headers=_auth(editor["access"]),
    )
    assert published.status_code == 200, published.text
    assert published.json()["resource_folder"]["slug"]
