"""Routes FastAPI — projects (module 5)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import AuthContext, DbSession, Language, require_permission
from app.modules.projects.models import ProjectStage, ReviewStatus
from app.modules.projects.schemas import (
    ContributorsRequest,
    ProjectCategoryOut,
    ProjectCreate,
    ProjectOut,
    ReviewRequest,
)
from app.modules.projects.service import (
    add_contributor,
    get_public,
    list_admin_projects,
    list_projects,
    remove_contributor,
    review_project,
    submit_project,
)
from app.shared.pagination import Page, PageParams, page_params

router = APIRouter(tags=["projects"])


# ---- public ----------

@router.get("/categories", response_model=list[ProjectCategoryOut])
async def list_categories(db: DbSession, lang: Language) -> list[ProjectCategoryOut]:
    return await list_categories(db, lang)


@router.get(
    "/projects",
    response_model=Page[ProjectOut],
    summary="Catalogue publique (approuvés uniquement)",
)
async def catalogue(
    db: DbSession,
    lang: Language,
    params: Annotated[PageParams, Depends(page_params)],
    category_id: Annotated[int | None, Query(ge=1, description="Filtrer par catégorie")] = None,
    stage: Annotated[ProjectStage | None, Query(description="Filtrer par étape")] = None,
    is_featured: Annotated[bool | None, Query(description="Filtrer par projet en vedette")] = None,
    technology_id: Annotated[int | None, Query(ge=1, description="Filtrer par technologie")] = None,
    search: Annotated[str | None, Query(max_length=100, description="Recherche nom / résumé")] = None,
) -> Page[ProjectOut]:
    return await list_projects(
        db,
        lang,
        category_id=category_id,
        stage=stage,
        is_featured=is_featured,
        technology_id=technology_id,
        search=search,
        params=params,
    )


@router.get("/projects/{slug}", response_model=ProjectOut, summary="Fiche d'un projet")
async def project_fiche(slug: str, db: DbSession, lang: Language) -> ProjectOut:
    return await get_public(db, slug, lang)


# ---- admin (géré par `project.review`) ----------

@router.post(
    "/admin/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Soumettre un projet (permission: project.submit)",
)
async def create_project(
    body: ProjectCreate,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission("project.submit"))],
    lang: Language,
) -> ProjectOut:
    return await submit_project(db, body, auth)


@router.get(
    "/admin/projects",
    response_model=Page[ProjectOut],
    summary="Catalogue admin (tous les statuts, avec filtres)",
)
async def admin_catalogue(
    db: DbSession,
    lang: Language,
    params: Annotated[PageParams, Depends(page_params)],
    category_id: Annotated[int | None, Query(ge=1)] = None,
    stage: Annotated[ProjectStage | None, Query()] = None,
    is_featured: Annotated[bool | None, Query()] = None,
    review_status: Annotated[ReviewStatus | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ProjectOut]:
    return await list_admin_projects(
        db,
        lang,
        category_id=category_id,
        stage=stage,
        is_featured=is_featured,
        review_status=review_status,
        search=search,
        params=params,
    )


@router.post(
    "/admin/projects/{slug}/review",
    response_model=ProjectOut,
    summary="Valider ou rejeter un projet (permission: project.review)",
)
async def admin_review(
    slug: str,
    body: ReviewRequest,
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("project.review"))],
    lang: Language,
) -> ProjectOut:
    action = body.action
    if action not in {"approve", "reject"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "action invalide", "code": "invalid_action"},
        )
    return await review_project(db, slug, action)


@router.post(
    "/admin/projects/{slug}/contributors",
    response_model=ProjectOut,
    summary="Ajouter des contributeurs (permission: project.review)",
)
async def admin_add_contributors(
    slug: str,
    body: ContributorsRequest,
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("project.review"))],
    lang: Language,
) -> ProjectOut:
    return await add_contributor(db, slug, body.contributor_ids, _auth)


@router.delete(
    "/admin/projects/{slug}/contributors/{user_id}",
    response_model=ProjectOut,
    summary="Retirer un contributeur (permission: project.review)",
)
async def admin_remove_contributor(
    slug: str,
    user_id: uuid.UUID,
    db: DbSession,
    _auth: Annotated[AuthContext, Depends(require_permission("project.review"))],
    lang: Language,
) -> ProjectOut:
    return await remove_contributor(db, slug, user_id)


# ---- status ----------

@router.get("/status", response_model=dict[str, str], summary="Statut du module")
async def projects_status() -> dict[str, str]:
    return {"module": "projects", "status": "ready"}
