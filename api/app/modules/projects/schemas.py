"""Schémas Pydantic — projects (module 5)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.modules.projects.models import ProjectStage, ReviewStatus


class ProjectCategoryCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    position: int = Field(default=0, ge=0)
    translations: list[ProjectCategoryTranslationIn] = Field(min_length=1)


class ProjectCategoryTranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    name: str


class ProjectCategoryOut(BaseModel):
    id: int
    slug: str
    position: int
    name: str
    language: str


class ProjectCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category_id: int | None = Field(default=None, ge=1)
    stage: ProjectStage = ProjectStage.idea
    license: str | None = Field(default=None, max_length=50)
    repo_url: str | None = None
    demo_url: str | None = None
    website_url: str | None = None
    logo_media_id: uuid.UUID | None = None
    is_featured: bool = False
    summary: str = Field(min_length=10, max_length=2000)
    description: str | None = Field(default=None, max_length=10000)
    translations: list[ProjectTranslationIn] = Field(min_length=1)
    technology_ids: list[int] | None = Field(default=None, max_length=50)
    contributor_ids: list[int] | None = Field(default=None, max_length=50)


class ProjectUpdate(BaseModel):
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: int | None = Field(default=None, ge=1)
    stage: ProjectStage | None = None
    license: str | None = Field(default=None, max_length=50)
    repo_url: str | None = None
    demo_url: str | None = None
    website_url: str | None = None
    logo_media_id: uuid.UUID | None = None
    is_featured: bool | None = None
    summary: str | None = Field(default=None, min_length=10, max_length=2000)
    description: str | None = Field(default=None, max_length=10000)
    translations: list[ProjectTranslationIn] | None = None
    technology_ids: list[int] | None = Field(default=None, max_length=50)
    contributor_ids: list[int] | None = Field(default=None, max_length=50)


class ProjectTranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    summary: str
    description: str | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    category_id: int | None
    stage: ProjectStage
    license: str | None
    repo_url: str | None
    demo_url: str | None
    website_url: str | None
    is_featured: bool
    review_status: ReviewStatus
    summary: str
    description: str | None
    language: str
    technologies: list[dict[str, Any]] = Field(default_factory=list)
    contributors: list[ProjectContributorOut] = Field(default_factory=list)


class ProjectContributorOut(BaseModel):
    user_id: uuid.UUID
    handle: str
    role: str


class ProjectsStatus(BaseModel):
    module: str = "projects"
    status: str = "ready"


class ReviewRequest(BaseModel):
    action: str = Field(min_length=1, max_length=10)


class ContributorsRequest(BaseModel):
    contributor_ids: list[int] = Field(min_length=1)
