"""Logique métier — projects (module 5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.members.models import MemberProfile, Technology
from app.modules.projects.models import (
    Project,
    ProjectCategory,
    ProjectContributor,
    ProjectStage,
    ProjectTechnology,
    ProjectTranslation,
    ReviewStatus,
)
from app.modules.projects.schemas import ProjectCategoryOut, ProjectContributorOut, ProjectOut
from app.shared.i18n import pick_translation
from app.shared.pagination import Page, PageParams, page_params

# ---- catégories -----------------------------------------------------------

async def list_categories(db: AsyncSession, lang: str) -> list[ProjectCategoryOut]:
    rows = (
        await db.execute(
            select(ProjectCategory)
            .options(selectinload(ProjectCategory.translations))
            .order_by(ProjectCategory.position, ProjectCategory.slug)
        )
    ).scalars().all()
    out: list[ProjectCategoryOut] = []
    for cat in rows:
        tr = pick_translation(cat.translations, lang)
        if tr is None:
            continue
        out.append(
            ProjectCategoryOut(
                id=cat.id,
                slug=cat.slug,
                position=cat.position,
                name=tr.name,
                language=tr.language_code,
            )
        )
    return out


# ---- catalogue public -----------------------------------------------------

async def list_projects(
    db: AsyncSession,
    lang: str,
    *,
    category_id: int | None = None,
    stage: ProjectStage | None = None,
    is_featured: bool | None = None,
    technology_id: int | None = None,
    search: str | None = None,
    params: PageParams | None = None,
) -> Page[ProjectOut]:
    params = params or page_params()
    stmt = select(Project).where(Project.review_status == ReviewStatus.approved)

    if category_id is not None:
        stmt = stmt.where(Project.category_id == category_id)
    if stage is not None:
        stmt = stmt.where(Project.stage == stage)
    if is_featured is not None:
        stmt = stmt.where(Project.is_featured == is_featured)
    if technology_id is not None:
        stmt = stmt.where(
            exists()
            .where(
                ProjectTechnology.project_id == Project.id,
                ProjectTechnology.technology_id == technology_id,
            )
            .correlate(Project)
        )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Project.name.ilike(like),
                ProjectTranslation.summary.ilike(like),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.offset(params.offset).limit(params.page_size).options(
        selectinload(Project.translations),
        selectinload(Project.category),
        selectinload(Project.technologies),
    )
    rows = (await db.execute(stmt)).scalars().all()

    items = [await to_project_out(db, p, lang) for p in rows]
    return Page[ProjectOut].of(items, total, params)


# ---- fiche ---------------------------------------------------------------

async def get_project(
    db: AsyncSession,
    slug: str,
    lang: str,
    *,
    public: bool = False,
) -> ProjectOut:
    stmt = select(Project).where(Project.slug == slug)
    if public:
        stmt = stmt.where(Project.review_status == ReviewStatus.approved)
    stmt = stmt.options(
        selectinload(Project.translations),
        selectinload(Project.category),
        selectinload(Project.technologies),
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Projet introuvable", "code": "project_not_found"},
        )
    return await to_project_out(db, project, lang)


async def get_public(db: AsyncSession, slug: str, lang: str) -> ProjectOut:
    return await get_project(db, slug, lang, public=True)


# ---- soumission ----------------------------------------------------------

async def submit_project(
    db: AsyncSession,
    body: Any,
    auth: Any,
) -> ProjectOut:
    if body.category_id is not None:
        cat = (
            await db.execute(
                select(ProjectCategory).where(ProjectCategory.id == body.category_id)
            )
        ).scalar_one_or_none()
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Catégorie introuvable", "code": "category_not_found"},
            )

    seen: set[int] = set()
    for tid in body.technology_ids or []:
        tech = (
            await db.execute(select(Technology).where(Technology.id == tid))
        ).scalar_one_or_none()
        if tech is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Technologie introuvable", "code": "technology_not_found"},
            )
        if tid in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Technologie dupliquée", "code": "duplicate_technology"},
            )
        seen.add(tid)

    for uid in body.contributor_ids or []:
        if uid == auth.user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Impossible de s'ajouter soi-même", "code": "self_contributor"},
            )
        member = (
            await db.execute(
                select(MemberProfile).where(MemberProfile.user_id == uid)
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Membre introuvable", "code": "member_not_found"},
            )

    project = Project(
        slug=body.slug,
        name=body.name,
        category_id=body.category_id,
        stage=body.stage,
        license=body.license,
        repo_url=body.repo_url,
        demo_url=body.demo_url,
        website_url=body.website_url,
        logo_media_id=body.logo_media_id,
        is_featured=body.is_featured,
        review_status=ReviewStatus.pending,
        submitted_by=auth.user.id,
    )
    db.add(project)
    await db.flush()

    for tr in body.translations:
        db.add(
            ProjectTranslation(
                project_id=project.id,
                language_code=tr.language_code,
                summary=tr.summary,
                description=tr.description,
            )
        )

    for tid in body.technology_ids or []:
        db.add(ProjectTechnology(project_id=project.id, technology_id=tid))

    for uid in body.contributor_ids or []:
        db.add(
            ProjectContributor(
                project_id=project.id,
                user_id=uid,
                role="contributor",
            )
        )

    await db.commit()
    await db.expire_all()
    return await get_project(db, body.slug, body.translations[0].language_code, public=False)


# ---- admin ---------------------------------------------------------------

async def list_admin_projects(
    db: AsyncSession,
    lang: str,
    *,
    category_id: int | None = None,
    stage: ProjectStage | None = None,
    is_featured: bool | None = None,
    review_status: ReviewStatus | None = None,
    search: str | None = None,
    params: PageParams | None = None,
) -> Page[ProjectOut]:
    params = params or page_params()
    stmt = select(Project)

    if category_id is not None:
        stmt = stmt.where(Project.category_id == category_id)
    if stage is not None:
        stmt = stmt.where(Project.stage == stage)
    if is_featured is not None:
        stmt = stmt.where(Project.is_featured == is_featured)
    if review_status is not None:
        stmt = stmt.where(Project.review_status == review_status)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Project.name.ilike(like),
                ProjectTranslation.summary.ilike(like),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.offset(params.offset).limit(params.page_size).options(
        selectinload(Project.translations),
        selectinload(Project.category),
        selectinload(Project.technologies),
    )
    rows = (await db.execute(stmt)).scalars().all()

    items = [await to_project_out(db, p, lang) for p in rows]
    return Page[ProjectOut].of(items, total, params)


async def review_project(db: AsyncSession, slug: str, action: str) -> ProjectOut:
    project = (
        await db.execute(
            select(Project).where(Project.slug == slug).options(selectinload(Project.translations))
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Projet introuvable", "code": "project_not_found"},
        )
    if action == "approve":
        project.review_status = ReviewStatus.approved
        project.reviewed_by = uuid.uuid4()
        project.reviewed_at = datetime_utc()
    elif action == "reject":
        project.review_status = ReviewStatus.rejected
        project.reviewed_by = uuid.uuid4()
        project.reviewed_at = datetime_utc()
        if project.rejection_reason is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "raison de rejet requise", "code": "rejection_reason_required"},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "action invalide", "code": "invalid_action"},
        )

    await db.commit()
    await db.expire_all()
    return await get_project(db, slug, "fr", public=False)


async def add_contributor(db: AsyncSession, slug: str, contributor_ids: list[int], auth: Any) -> ProjectOut:
    project = (
        await db.execute(
            select(Project).where(Project.slug == slug).options(selectinload(Project.contributors))
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Projet introuvable", "code": "project_not_found"},
        )

    for uid in contributor_ids:
        if uid == auth.user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Impossible de s'ajouter soi-même", "code": "self_contributor"},
            )
        member = (
            await db.execute(
                select(MemberProfile).where(MemberProfile.user_id == uid)
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Membre introuvable", "code": "member_not_found"},
            )

    for uid in contributor_ids:
        existing = (
            await db.execute(
                select(ProjectContributor).where(
                    ProjectContributor.project_id == project.id,
                    ProjectContributor.user_id == uid,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing.deleted_at is None:
            continue
        if existing is None or existing.deleted_at is not None:
            db.add(
                ProjectContributor(
                    project_id=project.id,
                    user_id=uid,
                    role="contributor",
                )
            )

    await db.commit()
    await db.expire_all()
    return await get_project(db, slug, "fr", public=False)


async def remove_contributor(db: AsyncSession, slug: str, user_id: uuid.UUID) -> ProjectOut:
    project = (
        await db.execute(
            select(Project).where(Project.slug == slug).options(selectinload(Project.contributors))
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Projet introuvable", "code": "project_not_found"},
        )

    contributor = (
        await db.execute(
            select(ProjectContributor).where(
                ProjectContributor.project_id == project.id,
                ProjectContributor.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if contributor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Contributeur introuvable", "code": "contributor_not_found"},
        )

    # Suppression LOGIQUE : on garde la ligne (récupération possible) et on
    # consigne la date de suppression.
    contributor.deleted_at = datetime_utc()
    await db.commit()
    await db.expire_all()
    return await get_project(db, slug, "fr", public=False)


# ---- helpers -------------------------------------------------------------

async def to_project_out(
    db: AsyncSession,
    project: Project,
    lang: str,
    *,
    technology_ids: list[int] | None = None,
) -> ProjectOut:
    tr = pick_translation(project.translations, lang)
    if tr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Traduction manquante", "code": "translation_missing"},
        )

    technologies: list[dict[str, Any]] = []
    if project.technologies:
        for pt in project.technologies:
            tech = pt.technology
            if tech is None:
                continue
            technologies.append(
                {
                    "id": tech.id,
                    "slug": tech.slug,
                    "name": tech.name,
                    "category": tech.category,
                }
            )

    contributors: list[ProjectContributorOut] = []
    contributor_ids = {c.user_id for c in project.contributors}
    profile_by_id: dict[uuid.UUID, MemberProfile] = {}
    if contributor_ids:
        rows = (
            await db.execute(
                select(MemberProfile).where(MemberProfile.user_id.in_(contributor_ids))
            )
        ).scalars().all()
        profile_by_id = {p.user_id: p for p in rows}

    for c in project.contributors:
        if c.deleted_at is not None:
            continue
        profile = profile_by_id.get(c.user_id)
        handle = profile.handle if profile is not None else ""
        contributors.append(
            ProjectContributorOut(
                user_id=c.user_id,
                handle=handle,
                role=c.role,
            )
        )

    return ProjectOut(
        id=project.id,
        slug=project.slug,
        name=project.name,
        category_id=project.category_id,
        stage=project.stage,
        license=project.license,
        repo_url=project.repo_url,
        demo_url=project.demo_url,
        website_url=project.website_url,
        is_featured=project.is_featured,
        review_status=project.review_status,
        summary=tr.summary,
        description=tr.description,
        language=tr.language_code,
        technologies=technologies,
        contributors=contributors,
    )


def datetime_utc() -> datetime:
    return datetime.now(UTC)
