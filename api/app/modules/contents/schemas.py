"""Schémas Pydantic — contents (module 1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

ContentStatusLiteral = Literal["draft", "in_review", "published", "archived"]


class TranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    title: str
    summary: str | None = None
    body: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None


class PageOut(BaseModel):
    id: uuid.UUID
    slug: str
    status: str
    published_at: datetime | None
    language: str
    title: str
    summary: str | None = None
    body: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None


class PageAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    status: str
    published_at: datetime | None
    cover_media_id: uuid.UUID | None
    translations: list[TranslationIn]


class PageCreate(BaseModel):
    slug: str
    status: ContentStatusLiteral = "draft"
    published_at: datetime | None = None
    cover_media_id: uuid.UUID | None = None
    translations: list[TranslationIn] = Field(min_length=1)


class PageUpdate(BaseModel):
    status: ContentStatusLiteral | None = None
    published_at: datetime | None = None
    cover_media_id: uuid.UUID | None = None
    translations: list[TranslationIn] | None = None


class TeamMemberOut(BaseModel):
    id: uuid.UUID
    full_name: str
    team_group: str
    linkedin_url: str | None
    position: int
    photo_media_id: uuid.UUID | None
    language: str
    role_title: str
    bio: str | None = None


class TeamMemberTranslationIn(BaseModel):
    language_code: str
    role_title: str
    bio: str | None = None


class TeamMemberCreate(BaseModel):
    full_name: str
    team_group: Literal["board", "team"] = "team"
    linkedin_url: str | None = None
    position: int = 0
    photo_media_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    is_active: bool = True
    translations: list[TeamMemberTranslationIn] = Field(min_length=1)


class TeamMemberUpdate(BaseModel):
    full_name: str | None = None
    team_group: Literal["board", "team"] | None = None
    linkedin_url: str | None = None
    position: int | None = None
    photo_media_id: uuid.UUID | None = None
    is_active: bool | None = None
    translations: list[TeamMemberTranslationIn] | None = None


class PartnerOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    website_url: str | None
    logo_media_id: uuid.UUID | None
    show_on_home: bool
    position: int
    level_code: str | None = None
    level_name: str | None = None
    language: str
    description: str | None = None


class PartnerCreate(BaseModel):
    slug: str
    name: str
    website_url: str | None = None
    logo_media_id: uuid.UUID | None = None
    level_id: int | None = None
    show_on_home: bool = False
    position: int = 0
    is_active: bool = True
    description_fr: str | None = None
    description_en: str | None = None


class PartnerUpdate(BaseModel):
    name: str | None = None
    website_url: str | None = None
    logo_media_id: uuid.UUID | None = None
    level_id: int | None = None
    show_on_home: bool | None = None
    position: int | None = None
    is_active: bool | None = None
    description_fr: str | None = None
    description_en: str | None = None


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    subject: str | None = None
    message: str = Field(min_length=1, max_length=5000)
    website: str | None = Field(default=None, description="Honeypot — doit rester vide")


class ContactOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    subject: str | None
    message: str
    language_code: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactStatusUpdate(BaseModel):
    status: Literal["new", "read", "handled", "spam"]


class ArticleOut(BaseModel):
    id: uuid.UUID
    slug: str
    status: str
    published_at: datetime | None
    category_id: int | None
    cover_media_id: uuid.UUID | None
    language: str
    title: str
    excerpt: str | None = None
    body: str | None = None
    tags: list[str] = []


class ArticleCreate(BaseModel):
    slug: str
    category_id: int | None = None
    cover_media_id: uuid.UUID | None = None
    status: ContentStatusLiteral = "draft"
    published_at: datetime | None = None
    tag_ids: list[int] = []
    translations: list[TranslationIn] = Field(min_length=1)


class ArticleUpdate(BaseModel):
    category_id: int | None = None
    cover_media_id: uuid.UUID | None = None
    status: ContentStatusLiteral | None = None
    published_at: datetime | None = None
    tag_ids: list[int] | None = None
    translations: list[TranslationIn] | None = None


class KeyFigureOut(BaseModel):
    id: int
    code: str
    value: Decimal
    suffix: str | None
    language: str
    label: str
    position: int


class KeyFigureUpdate(BaseModel):
    value: Decimal | None = None
    suffix: str | None = None
    show_on_home: bool | None = None
    position: int | None = None
    is_active: bool | None = None
    label_fr: str | None = None
    label_en: str | None = None


class EventTeaserOut(BaseModel):
    id: uuid.UUID
    slug: str
    starts_at: datetime
    city: str | None
    language: str
    title: str
    summary: str | None = None


class HomeOut(BaseModel):
    page: PageOut | None
    key_figures: list[KeyFigureOut]
    partners: list[PartnerOut]
    upcoming_events: list[EventTeaserOut]
    latest_articles: list[ArticleOut]


class MessageResponse(BaseModel):
    detail: str
    code: str = "ok"


class ContentsStatus(BaseModel):
    module: str = "contents"
    status: str = "ready"
