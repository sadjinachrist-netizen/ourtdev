"""Schémas Pydantic — festival (module 4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

ContentStatusLiteral = Literal["draft", "in_review", "published", "archived"]
AnnouncementKind = Literal["registration", "call_for_speakers", "ticketing", "other"]


class EditionTranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    theme: str | None = None
    summary: str | None = None
    description: str | None = None


class EditionCreate(BaseModel):
    year: int = Field(ge=2020, le=2100)
    starts_on: date | None = None
    ends_on: date | None = None
    city: str | None = None
    venue: str | None = None
    target_url: str | None = None
    is_current: bool = False
    status: ContentStatusLiteral = "draft"
    published_at: datetime | None = None
    translations: list[EditionTranslationIn] = Field(min_length=1)


class EditionUpdate(BaseModel):
    starts_on: date | None = None
    ends_on: date | None = None
    city: str | None = None
    venue: str | None = None
    target_url: str | None = None
    is_current: bool | None = None
    status: ContentStatusLiteral | None = None
    published_at: datetime | None = None
    translations: list[EditionTranslationIn] | None = None


class FigureCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    value: Decimal
    suffix: str | None = None
    label_fr: str
    label_en: str | None = None
    position: int = 0


class FigureOut(BaseModel):
    id: int
    code: str
    value: Decimal
    suffix: str | None = None
    language: str
    label: str
    position: int


class EditionOut(BaseModel):
    year: int
    starts_on: date | None = None
    ends_on: date | None = None
    city: str | None = None
    venue: str | None = None
    target_url: str | None = None
    is_current: bool
    status: str
    published_at: datetime | None = None
    language: str
    theme: str | None = None
    summary: str | None = None
    description: str | None = None
    figures: list[FigureOut] = []


class FestivalPage(BaseModel):
    current: EditionOut | None = None
    archive: list[EditionOut] = []


class AnnouncementTranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    message: str
    cta_label: str | None = None


class AnnouncementCreate(BaseModel):
    edition_year: int | None = Field(default=None, ge=2020, le=2100)
    kind: AnnouncementKind = "other"
    cta_url: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    is_active: bool = True
    position: int = 0
    translations: list[AnnouncementTranslationIn] = Field(min_length=1)


class AnnouncementUpdate(BaseModel):
    kind: AnnouncementKind | None = None
    cta_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    position: int | None = None
    translations: list[AnnouncementTranslationIn] | None = None


class AnnouncementOut(BaseModel):
    id: uuid.UUID
    edition_year: int | None = None
    kind: str
    message: str
    cta_label: str | None = None
    cta_url: str | None = None
    language: str
    position: int


class RedirectCreate(BaseModel):
    source_path: str = Field(pattern=r"^/.*")
    target_url: str
    status_code: Literal[301, 302] = 301
    is_active: bool = True


class RedirectUpdate(BaseModel):
    target_url: str | None = None
    status_code: Literal[301, 302] | None = None
    is_active: bool | None = None


class RedirectOut(BaseModel):
    id: int
    source_path: str
    target_url: str
    status_code: int
    is_active: bool
    hit_count: int


class FestivalStatus(BaseModel):
    module: str = "festival"
    status: str = "ready"
