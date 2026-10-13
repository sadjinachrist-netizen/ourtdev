"""Couverture des routes déjà implémentées : socle, contenus, membres."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.modules.auth import service as auth_service
from app.shared.rate_limit import contact_rate_limiter

API = "/api/v1"
PASSWORD = "motdepasse1"


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    messages: list[str] = []

    async def capture(*, to: str, subject: str, body: str) -> None:
        messages.append(body)

    monkeypatch.setattr(auth_service, "send_email", capture)
    return messages


def _token(body: str) -> str:
    match = re.search(r"token=([^\s&]+)", body)
    assert match is not None
    return match.group(1)


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


async def _register(client: AsyncClient, inbox: list[str]) -> dict[str, str]:
    email = f"u{uuid.uuid4().hex[:10]}@test.tdev"
    created = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "preferred_language": "fr"},
    )
    assert created.status_code == 201, created.text
    assert inbox, "l'email de vérification doit être envoyé"
    verified = await client.post(
        f"{API}/auth/verify-email",
        json={"token": _token(inbox[-1])},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "active"
    logged = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert logged.status_code == 200, logged.text
    body = logged.json()
    return {
        "email": email,
        "user_id": created.json()["id"],
        "access": body["access_token"],
        "refresh": body["refresh_token"],
    }


async def test_socle_auth_settings_media(client: AsyncClient, inbox: list[str]) -> None:
    health = await client.get(f"{API}/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    for path in ("/auth/status", "/users/status", "/media/status"):
        status = await client.get(f"{API}{path}")
        assert status.status_code == 200, path

    user = await _register(client, inbox)
    headers = _auth(user["access"])

    me = await client.get(f"{API}/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]

    refreshed = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": user["refresh"]},
    )
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]

    logged_out = await client.post(
        f"{API}/auth/logout",
        json={"refresh_token": new_refresh},
    )
    assert logged_out.status_code == 200
    reused = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert reused.status_code == 401

    forgot = await client.post(
        f"{API}/auth/forgot-password",
        json={"email": user["email"]},
    )
    assert forgot.status_code == 200
    reset = await client.post(
        f"{API}/auth/reset-password",
        json={"token": _token(inbox[-1]), "new_password": "nouveau-mdp1"},
    )
    assert reset.status_code == 200
    relogin = await client.post(
        f"{API}/auth/login",
        json={"email": user["email"], "password": "nouveau-mdp1"},
    )
    assert relogin.status_code == 200
    headers = _auth(relogin.json()["access_token"])

    github = await client.get(f"{API}/auth/oauth/github/authorize")
    assert github.status_code == 503
    google = await client.get(f"{API}/auth/oauth/google/authorize")
    assert google.status_code == 503

    await _grant(user["user_id"], "admin")
    setup = await client.post(f"{API}/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = await client.post(
        f"{API}/auth/mfa/enable",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["recovery_codes"]

    challenged = await client.post(
        f"{API}/auth/login",
        json={"email": user["email"], "password": "nouveau-mdp1"},
    )
    assert challenged.status_code == 200
    assert challenged.json()["mfa_required"] is True
    verified_mfa = await client.post(
        f"{API}/auth/mfa/verify",
        json={
            "mfa_ticket": challenged.json()["mfa_ticket"],
            "code": enabled.json()["recovery_codes"][0],
        },
    )
    assert verified_mfa.status_code == 200, verified_mfa.text
    assert verified_mfa.json()["access_token"]

    public_settings = await client.get(f"{API}/settings")
    assert public_settings.status_code == 200
    keys = {row["key"] for row in public_settings.json()}
    assert "site_name" in keys

    member = await _register(client, inbox)
    forbidden = await client.get(f"{API}/settings/all", headers=_auth(member["access"]))
    assert forbidden.status_code == 403

    admin_headers = _auth(verified_mfa.json()["access_token"])
    all_settings = await client.get(f"{API}/settings/all", headers=admin_headers)
    assert all_settings.status_code == 200
    current = next(row for row in all_settings.json() if row["key"] == "site_name")
    patched = await client.patch(
        f"{API}/settings/site_name",
        headers=admin_headers,
        json={"value": "TDEV test"},
    )
    assert patched.status_code == 200
    assert patched.json()["value"] == "TDEV test"
    restored = await client.patch(
        f"{API}/settings/site_name",
        headers=admin_headers,
        json={"value": current["value"]},
    )
    assert restored.status_code == 200

    denied_upload = await client.post(
        f"{API}/media",
        headers=_auth(member["access"]),
        files={"file": ("note.txt", b"bonjour", "text/plain")},
    )
    assert denied_upload.status_code == 403
    uploaded = await client.post(
        f"{API}/media",
        headers=admin_headers,
        files={"file": ("note.txt", b"bonjour", "text/plain")},
        data={"alt_text": "note", "language_code": "fr"},
    )
    assert uploaded.status_code == 200, uploaded.text
    media = await client.get(f"{API}/media/{uploaded.json()['id']}")
    assert media.status_code == 200
    assert media.json()["original_name"] == "note.txt"


async def test_module_contents(client: AsyncClient, inbox: list[str]) -> None:
    contact_rate_limiter._hits.clear()
    editor = await _register(client, inbox)
    await _grant(editor["user_id"], "editor")
    headers = _auth(editor["access"])
    suffix = uuid.uuid4().hex[:8]
    now = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    for path in ("/home", "/team", "/partners", "/articles", "/contents/status"):
        response = await client.get(f"{API}{path}")
        assert response.status_code == 200, path

    member = await _register(client, inbox)
    denied = await client.get(f"{API}/admin/pages", headers=_auth(member["access"]))
    assert denied.status_code == 403

    created_page = await client.post(
        f"{API}/admin/pages",
        headers=headers,
        json={
            "slug": f"page-{suffix}",
            "status": "draft",
            "translations": [
                {"language_code": "fr", "title": "Page FR", "body": "corps"},
                {"language_code": "en", "title": "Page EN", "body": "body"},
            ],
        },
    )
    assert created_page.status_code == 201, created_page.text
    page_id = created_page.json()["id"]
    updated_page = await client.patch(
        f"{API}/admin/pages/{page_id}",
        headers=headers,
        json={"status": "published", "published_at": now},
    )
    assert updated_page.status_code == 200
    public_fr = await client.get(f"{API}/pages/page-{suffix}?lang=fr")
    public_en = await client.get(f"{API}/pages/page-{suffix}?lang=en")
    assert public_fr.json()["title"] == "Page FR"
    assert public_en.json()["title"] == "Page EN"
    listed = await client.get(f"{API}/admin/pages", headers=headers)
    assert any(row["slug"] == f"page-{suffix}" for row in listed.json())

    created_team = await client.post(
        f"{API}/admin/team",
        headers=headers,
        json={
            "full_name": f"Ada {suffix}",
            "team_group": "board",
            "translations": [{"language_code": "fr", "role_title": "Présidente"}],
        },
    )
    assert created_team.status_code == 201, created_team.text
    team_id = created_team.json()["id"]
    patched_team = await client.patch(
        f"{API}/admin/team/{team_id}",
        headers=headers,
        json={"translations": [{"language_code": "fr", "role_title": "Trésorière"}]},
    )
    assert patched_team.status_code == 200
    team = await client.get(f"{API}/team")
    assert any(row["full_name"] == f"Ada {suffix}" for row in team.json())

    created_partner = await client.post(
        f"{API}/admin/partners",
        headers=headers,
        json={"slug": f"part-{suffix}", "name": f"Partenaire {suffix}", "show_on_home": True},
    )
    assert created_partner.status_code == 201, created_partner.text
    partner_id = created_partner.json()["id"]
    patched_partner = await client.patch(
        f"{API}/admin/partners/{partner_id}",
        headers=headers,
        json={"website_url": "https://partenaire.tdev"},
    )
    assert patched_partner.status_code == 200
    partners = await client.get(f"{API}/partners")
    assert any(row["slug"] == f"part-{suffix}" for row in partners.json())

    created_article = await client.post(
        f"{API}/admin/articles",
        headers=headers,
        json={
            "slug": f"actu-{suffix}",
            "status": "draft",
            "translations": [{"language_code": "fr", "title": "Actu", "body": "texte"}],
        },
    )
    assert created_article.status_code == 201, created_article.text
    article_id = created_article.json()["id"]
    patched_article = await client.patch(
        f"{API}/admin/articles/{article_id}",
        headers=headers,
        json={"status": "published", "published_at": now},
    )
    assert patched_article.status_code == 200
    article = await client.get(f"{API}/articles/actu-{suffix}")
    assert article.status_code == 200
    assert article.json()["title"] == "Actu"
    articles = await client.get(f"{API}/articles")
    assert any(row["slug"] == f"actu-{suffix}" for row in articles.json())

    honeypot = await client.post(
        f"{API}/contact",
        json={
            "name": "Bot",
            "email": "bot@test.tdev",
            "message": "spam",
            "website": "https://spam.example",
        },
    )
    assert honeypot.status_code == 400
    sent = await client.post(
        f"{API}/contact",
        json={"name": f"Visiteur {suffix}", "email": f"v{suffix}@test.tdev", "message": "Bonjour"},
    )
    assert sent.status_code == 201, sent.text
    inbox_admin = await client.get(f"{API}/admin/contact", headers=headers)
    assert inbox_admin.status_code == 200
    message = next(row for row in inbox_admin.json() if row["name"] == f"Visiteur {suffix}")
    handled = await client.patch(
        f"{API}/admin/contact/{message['id']}",
        headers=headers,
        json={"status": "handled"},
    )
    assert handled.status_code == 200
    assert handled.json()["status"] == "handled"

    figures = await client.get(f"{API}/admin/key-figures", headers=headers)
    assert figures.status_code == 200
    figure = figures.json()[0]
    updated_figure = await client.patch(
        f"{API}/admin/key-figures/{figure['id']}",
        headers=headers,
        json={"label_fr": figure["label"]},
    )
    assert updated_figure.status_code == 200
    assert updated_figure.json()["code"] == figure["code"]


async def test_module_members(client: AsyncClient, inbox: list[str]) -> None:
    contact_rate_limiter._hits.clear()
    member = await _register(client, inbox)
    editor = await _register(client, inbox)
    admin = await _register(client, inbox)
    await _grant(editor["user_id"], "editor")
    await _grant(admin["user_id"], "admin")
    member_headers = _auth(member["access"])
    editor_headers = _auth(editor["access"])
    admin_headers = _auth(admin["access"])
    suffix = uuid.uuid4().hex[:8]

    status = await client.get(f"{API}/members/status")
    assert status.status_code == 200
    assert status.json()["status"] == "ready"

    technologies = await client.get(f"{API}/technologies")
    assert technologies.status_code == 200
    denied_tech = await client.post(
        f"{API}/admin/technologies",
        headers=member_headers,
        json={"slug": f"x{suffix}", "name": f"X {suffix}"},
    )
    assert denied_tech.status_code == 403
    created_tech = await client.post(
        f"{API}/admin/technologies",
        headers=editor_headers,
        json={"slug": f"py{suffix}", "name": f"Python {suffix}", "category": "langage"},
    )
    assert created_tech.status_code == 201, created_tech.text
    listed_tech = await client.get(f"{API}/technologies")
    assert any(row["slug"] == f"py{suffix}" for row in listed_tech.json())

    base_profile = {
        "handle": f"ada{suffix}",
        "display_name": f"Ada {suffix}",
        "title": "Dev",
        "city": "Lomé",
        "country_code": "TG",
        "visibility": "public",
        "listed_in_directory": True,
        "show_location": False,
        "show_links": False,
        "github_url": "https://github.com/ada",
        "technologies": [{"slug": f"py{suffix}", "level": 4}],
    }
    profile = await client.put(f"{API}/members/me", headers=member_headers, json=base_profile)
    assert profile.status_code == 200, profile.text
    own = await client.get(f"{API}/members/me", headers=member_headers)
    assert own.status_code == 200
    assert own.json()["city"] == "Lomé"
    assert own.json()["github_url"] == "https://github.com/ada"

    directory = await client.get(f"{API}/directory", params={"technology": f"py{suffix}", "q": f"ada{suffix}"})
    assert directory.status_code == 200
    assert any(row["handle"] == f"ada{suffix}" for row in directory.json()["items"])

    public = await client.get(f"{API}/directory/ada{suffix}")
    assert public.status_code == 200
    assert "email" not in public.json()
    assert public.json()["city"] is None
    assert public.json()["github_url"] is None

    hidden_members = await client.put(
        f"{API}/members/me",
        headers=member_headers,
        json={**base_profile, "visibility": "members", "show_location": True},
    )
    assert hidden_members.status_code == 200
    anonymous = await client.get(f"{API}/directory/ada{suffix}")
    assert anonymous.status_code == 404
    as_member = await client.get(f"{API}/directory/ada{suffix}", headers=editor_headers)
    assert as_member.status_code == 200
    assert as_member.json()["city"] == "Lomé"

    pii = await client.put(
        f"{API}/members/me/pii",
        headers=member_headers,
        json={"first_name": "Ada", "last_name": "Lovelace", "phone": "+22890000000"},
    )
    assert pii.status_code == 200
    own_pii = await client.get(f"{API}/members/me/pii", headers=member_headers)
    assert own_pii.json()["first_name"] == "Ada"
    editor_pii = await client.get(f"{API}/admin/members/{member['user_id']}/pii", headers=editor_headers)
    assert editor_pii.status_code == 403
    admin_pii = await client.get(f"{API}/admin/members/{member['user_id']}/pii", headers=admin_headers)
    assert admin_pii.status_code == 200
    assert admin_pii.json()["last_name"] == "Lovelace"

    dashboard = await client.get(f"{API}/members/me/dashboard", headers=member_headers)
    assert dashboard.status_code == 200
    assert dashboard.json() == {"events": [], "projects": [], "resources": []}

    pending = await client.post(
        f"{API}/auth/register",
        json={"email": f"pending{suffix}@test.tdev", "password": PASSWORD},
    )
    assert pending.status_code == 201
    denied_approve = await client.post(
        f"{API}/admin/members/{pending.json()['id']}/approve",
        headers=member_headers,
    )
    assert denied_approve.status_code == 403
    approved = await client.post(
        f"{API}/admin/members/{pending.json()['id']}/approve",
        headers=editor_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved_at"] is not None

    denied_badge = await client.post(
        f"{API}/admin/members/{member['user_id']}/badges",
        headers=member_headers,
        json={"code": "contributor"},
    )
    assert denied_badge.status_code == 403
    awarded = await client.post(
        f"{API}/admin/members/{member['user_id']}/badges",
        headers=editor_headers,
        json={"code": "contributor"},
    )
    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["badges"][0]["code"] == "contributor"

    denied_hide = await client.post(
        f"{API}/admin/members/{member['user_id']}/visibility",
        headers=member_headers,
        json={"hidden": True},
    )
    assert denied_hide.status_code == 403
    hidden = await client.post(
        f"{API}/admin/members/{member['user_id']}/visibility",
        headers=editor_headers,
        json={"hidden": True},
    )
    assert hidden.status_code == 200
    assert (await client.get(f"{API}/directory/ada{suffix}", headers=admin_headers)).status_code == 404
    shown = await client.post(
        f"{API}/admin/members/{member['user_id']}/visibility",
        headers=editor_headers,
        json={"hidden": False},
    )
    assert shown.status_code == 200

    denied_export = await client.get(f"{API}/admin/members/export", headers=member_headers)
    assert denied_export.status_code == 403
    editor_export = await client.get(f"{API}/admin/members/export", headers=editor_headers)
    assert editor_export.status_code == 403
    exported = await client.get(f"{API}/admin/members/export", headers=admin_headers)
    assert exported.status_code == 200
    assert f"ada{suffix}" in exported.text
    assert "Ada" in exported.text

    opened = await client.put(
        f"{API}/members/me",
        headers=member_headers,
        json={**base_profile, "visibility": "public", "show_location": True, "allow_contact": True},
    )
    assert opened.status_code == 200, opened.text

    spam = await client.post(
        f"{API}/directory/ada{suffix}/contact",
        json={
            "name": "Bot",
            "email": "bot@test.tdev",
            "message": "spam",
            "website": "https://spam.example",
        },
    )
    assert spam.status_code == 400
    contacted = await client.post(
        f"{API}/directory/ada{suffix}/contact",
        json={"name": "Visiteur", "email": "visiteur@test.tdev", "message": "Salut"},
    )
    assert contacted.status_code == 201, contacted.text
