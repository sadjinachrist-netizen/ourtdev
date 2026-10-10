"""Routes FastAPI — module 1 contenus."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import AuthContext, DbSession, Language, require_permission
from app.modules.contents.schemas import (
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    ContactCreate,
    ContactOut,
    ContactStatusUpdate,
    ContentsStatus,
    HomeOut,
    KeyFigureOut,
    KeyFigureUpdate,
    MessageResponse,
    PageAdminOut,
    PageCreate,
    PageOut,
    PageUpdate,
    PartnerCreate,
    PartnerOut,
    PartnerUpdate,
    TeamMemberCreate,
    TeamMemberOut,
    TeamMemberUpdate,
)
from app.modules.contents.service import ContentsService
from app.shared.rate_limit import client_ip, contact_rate_limiter

router = APIRouter(tags=["contents"])


# ----- public -----


@router.get("/home", response_model=HomeOut, summary="Page d'accueil agrégée")
async def home(db: DbSession, lang: Language) -> HomeOut:
    return await ContentsService(db).get_home(lang)


@router.get("/pages/{slug}", response_model=PageOut, summary="Page publique par slug")
async def get_page(slug: str, db: DbSession, lang: Language) -> PageOut:
    return await ContentsService(db).get_page(slug, lang, public=True)


@router.get("/team", response_model=list[TeamMemberOut], summary="Équipe et bureau")
async def list_team(db: DbSession, lang: Language) -> list[TeamMemberOut]:
    return await ContentsService(db).list_team(lang)


@router.get("/partners", response_model=list[PartnerOut], summary="Partenaires")
async def list_partners(db: DbSession, lang: Language) -> list[PartnerOut]:
    return await ContentsService(db).list_partners(lang)


@router.post(
    "/contact",
    response_model=MessageResponse,
    status_code=201,
    summary="Formulaire de contact",
)
async def post_contact(
    body: ContactCreate,
    request: Request,
    db: DbSession,
    lang: Language,
) -> MessageResponse:
    contact_rate_limiter.check(f"contact:{client_ip(request)}")
    await ContentsService(db).create_contact(body, lang)
    return MessageResponse(detail="Message envoyé", code="contact_sent")


@router.get("/articles", response_model=list[ArticleOut], summary="Liste des articles publiés")
async def list_articles(db: DbSession, lang: Language) -> list[ArticleOut]:
    return await ContentsService(db).list_articles(lang)


@router.get("/articles/{slug}", response_model=ArticleOut, summary="Article publié")
async def get_article(slug: str, db: DbSession, lang: Language) -> ArticleOut:
    return await ContentsService(db).get_article(slug, lang)


# ----- admin pages -----


@router.get(
    "/admin/pages",
    response_model=list[PageAdminOut],
    summary="Liste admin des pages",
)
async def admin_list_pages(
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> list[PageAdminOut]:
    return await ContentsService(db).list_pages_admin()


@router.post(
    "/admin/pages",
    response_model=PageAdminOut,
    status_code=201,
    summary="Créer une page",
)
async def admin_create_page(
    body: PageCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> PageAdminOut:
    return await ContentsService(db).create_page(body, auth)


@router.patch(
    "/admin/pages/{page_id}",
    response_model=PageAdminOut,
    summary="Modifier une page",
)
async def admin_update_page(
    page_id: uuid.UUID,
    body: PageUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> PageAdminOut:
    return await ContentsService(db).update_page(page_id, body, auth)


@router.post(
    "/admin/pages/{page_id}/publish",
    response_model=PageAdminOut,
    summary="Publier une page",
)
async def admin_publish_page(
    page_id: uuid.UUID,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> PageAdminOut:
    return await ContentsService(db).publish_page(page_id, auth)


# ----- admin team -----


@router.post(
    "/admin/team",
    response_model=TeamMemberOut,
    status_code=201,
    summary="Ajouter un membre d'équipe",
)
async def admin_create_team(
    body: TeamMemberCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> TeamMemberOut:
    return await ContentsService(db).create_team_member(body, auth)


@router.patch(
    "/admin/team/{member_id}",
    response_model=TeamMemberOut,
    summary="Modifier un membre d'équipe",
)
async def admin_update_team(
    member_id: uuid.UUID,
    body: TeamMemberUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("page.manage"))],
) -> TeamMemberOut:
    return await ContentsService(db).update_team_member(member_id, body, auth)


# ----- admin partners -----


@router.post(
    "/admin/partners",
    response_model=PartnerOut,
    status_code=201,
    summary="Créer un partenaire",
)
async def admin_create_partner(
    body: PartnerCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("partner.manage"))],
) -> PartnerOut:
    return await ContentsService(db).create_partner(body, auth)


@router.patch(
    "/admin/partners/{partner_id}",
    response_model=PartnerOut,
    summary="Modifier un partenaire",
)
async def admin_update_partner(
    partner_id: uuid.UUID,
    body: PartnerUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("partner.manage"))],
) -> PartnerOut:
    return await ContentsService(db).update_partner(partner_id, body, auth)


# ----- admin articles -----


@router.post(
    "/admin/articles",
    response_model=ArticleOut,
    status_code=201,
    summary="Créer un article",
)
async def admin_create_article(
    body: ArticleCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("article.manage"))],
) -> ArticleOut:
    return await ContentsService(db).create_article(body, auth)


@router.patch(
    "/admin/articles/{article_id}",
    response_model=ArticleOut,
    summary="Modifier un article",
)
async def admin_update_article(
    article_id: uuid.UUID,
    body: ArticleUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("article.manage"))],
) -> ArticleOut:
    return await ContentsService(db).update_article(article_id, body, auth)


# ----- admin contact / key figures -----


@router.get(
    "/admin/contact",
    response_model=list[ContactOut],
    summary="Messages de contact",
)
async def admin_list_contact(
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("contact.read"))],
) -> list[ContactOut]:
    return await ContentsService(db).list_contacts()


@router.patch(
    "/admin/contact/{message_id}",
    response_model=ContactOut,
    summary="Changer le statut d'un message",
)
async def admin_update_contact(
    message_id: uuid.UUID,
    body: ContactStatusUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("contact.read"))],
) -> ContactOut:
    return await ContentsService(db).update_contact_status(message_id, body.status, auth)


@router.get(
    "/admin/key-figures",
    response_model=list[KeyFigureOut],
    summary="Chiffres clés (admin)",
)
async def admin_list_key_figures(
    db: DbSession,
    lang: Language,
    _auth: Annotated[AuthContext, Depends(require_permission("key_figure.manage"))],
) -> list[KeyFigureOut]:
    return await ContentsService(db).list_key_figures(lang)


@router.patch(
    "/admin/key-figures/{figure_id}",
    response_model=KeyFigureOut,
    summary="Modifier un chiffre clé",
)
async def admin_update_key_figure(
    figure_id: int,
    body: KeyFigureUpdate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("key_figure.manage"))],
) -> KeyFigureOut:
    return await ContentsService(db).update_key_figure(figure_id, body, auth)


@router.get("/contents/status", response_model=ContentsStatus, summary="Statut module contents")
async def contents_status() -> ContentsStatus:
    return ContentsStatus()
