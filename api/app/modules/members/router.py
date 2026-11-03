"""Routes FastAPI — module 2 membres et annuaire."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.core.dependencies import (
    AuthContext,
    CurrentAuth,
    DbSession,
    Language,
    OptionalAuth,
    require_permission,
)
from app.modules.members.schemas import (
    ApproveOut,
    BadgeAward,
    DashboardOut,
    DirectoryItem,
    HideRequest,
    MemberContactCreate,
    MembersStatus,
    PiiOut,
    PiiUpsert,
    ProfileOut,
    ProfileUpsert,
    TechnologyCreate,
    TechnologyOut,
)
from app.modules.members.service import MembersService
from app.shared.pagination import Page, PageParams, page_params
from app.shared.rate_limit import client_ip, contact_rate_limiter
from app.shared.schemas import Message

router = APIRouter(tags=["members"])


@router.get("/directory", response_model=Page[DirectoryItem], summary="Annuaire public")
async def directory(
    db: DbSession,
    lang: Language,
    viewer: OptionalAuth,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query()] = None,
    technology: Annotated[str | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    country_code: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    member_status: Annotated[str | None, Query()] = None,
) -> Page[DirectoryItem]:
    return await MembersService(db).list_directory(
        lang=lang,
        viewer=viewer,
        q=q,
        technology=technology,
        city=city,
        country_code=country_code,
        member_status=member_status,
        params=params,
    )


@router.get("/directory/{handle}", response_model=ProfileOut, summary="Profil public")
async def public_profile(
    handle: str,
    db: DbSession,
    lang: Language,
    viewer: OptionalAuth,
) -> ProfileOut:
    return await MembersService(db).get_public_profile(handle, lang, viewer)


@router.post(
    "/directory/{handle}/contact",
    response_model=Message,
    status_code=201,
    summary="Contacter un membre sans exposer son email",
)
async def contact_member(
    handle: str,
    body: MemberContactCreate,
    request: Request,
    db: DbSession,
    viewer: OptionalAuth,
) -> Message:
    contact_rate_limiter.check(f"member-contact:{client_ip(request)}")
    await MembersService(db).contact_member(handle, body, viewer)
    return Message(detail="Message envoyé", code="member_contact_sent")


@router.get("/members/me", response_model=ProfileOut, summary="Mon profil")
async def my_profile(auth: CurrentAuth, db: DbSession, lang: Language) -> ProfileOut:
    return await MembersService(db).get_own_profile(auth, lang)


@router.put("/members/me", response_model=ProfileOut, summary="Créer ou modifier mon profil")
async def upsert_profile(
    body: ProfileUpsert,
    auth: CurrentAuth,
    db: DbSession,
    lang: Language,
) -> ProfileOut:
    if not auth.has_permission("profile.edit_own"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Permission requise: profile.edit_own", "code": "forbidden"},
        )
    return await MembersService(db).upsert_profile(auth, body, lang)


@router.get("/members/me/pii", response_model=PiiOut, summary="Mes données personnelles")
async def my_pii(auth: CurrentAuth, db: DbSession) -> PiiOut:
    return await MembersService(db).get_own_pii(auth)


@router.put("/members/me/pii", response_model=PiiOut, summary="Modifier mes données personnelles")
async def upsert_pii(body: PiiUpsert, auth: CurrentAuth, db: DbSession) -> PiiOut:
    return await MembersService(db).upsert_pii(auth, body)


@router.get("/members/me/dashboard", response_model=DashboardOut, summary="Mon tableau de bord")
async def my_dashboard(auth: CurrentAuth, db: DbSession) -> DashboardOut:
    return await MembersService(db).dashboard(auth)


@router.get("/technologies", response_model=list[TechnologyOut], summary="Compétences")
async def list_technologies(db: DbSession) -> list[TechnologyOut]:
    return await MembersService(db).list_technologies()


@router.post(
    "/admin/technologies",
    response_model=TechnologyOut,
    status_code=201,
    summary="Créer une compétence",
)
async def create_technology(
    body: TechnologyCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("member.moderate"))],
) -> TechnologyOut:
    return await MembersService(db).create_technology(body, auth)


@router.post(
    "/admin/members/{user_id}/approve",
    response_model=ApproveOut,
    summary="Valider une inscription",
)
async def approve_member(
    user_id: uuid.UUID,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("member.approve"))],
) -> ApproveOut:
    return await MembersService(db).approve(user_id, auth)


@router.post(
    "/admin/members/{user_id}/visibility",
    response_model=ProfileOut,
    summary="Masquer ou réafficher un profil",
)
async def hide_member(
    user_id: uuid.UUID,
    body: HideRequest,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("member.moderate"))],
) -> ProfileOut:
    return await MembersService(db).set_hidden(user_id, body.hidden, auth)


@router.post(
    "/admin/members/{user_id}/badges",
    response_model=ProfileOut,
    summary="Attribuer un badge",
)
async def award_badge(
    user_id: uuid.UUID,
    body: BadgeAward,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("member.moderate"))],
) -> ProfileOut:
    return await MembersService(db).award_badge(user_id, body, auth)


@router.get(
    "/admin/members/{user_id}/pii",
    response_model=PiiOut,
    summary="Lire les données personnelles",
)
async def admin_pii(
    user_id: uuid.UUID,
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("pii.read"))],
) -> PiiOut:
    return await MembersService(db).get_pii_admin(user_id)


@router.get("/admin/members/export", summary="Export CSV des membres")
async def export_members(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("member.export"))],
) -> Response:
    csv_body = await MembersService(db).export_csv(include_pii=auth.has_permission("pii.read"))
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=members.csv"},
    )


@router.get("/members/status", response_model=MembersStatus, summary="Statut module members")
async def members_status() -> MembersStatus:
    return MembersStatus()
