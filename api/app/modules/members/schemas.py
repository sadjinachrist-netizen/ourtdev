"""Schémas Pydantic — membres et annuaire."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

MemberStatusLiteral = Literal["student", "professional", "freelance", "recruiter", "other"]
AvailabilityLiteral = Literal["available", "open", "unavailable"]
VisibilityLiteral = Literal["public", "members", "private"]


class TechnologyIn(BaseModel):
    slug: str
    level: int | None = Field(default=None, ge=1, le=5)


class TechnologyOut(BaseModel):
    slug: str
    name: str
    category: str | None = None
    level: int | None = None


class TechnologyCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=40)
    name: str
    category: str | None = None


class BadgeOut(BaseModel):
    code: str
    name: str
    edition_year: int | None = None


class ProfileUpsert(BaseModel):
    handle: str = Field(pattern=r"^[a-z0-9_-]{3,30}$")
    display_name: str = Field(min_length=1, max_length=120)
    title: str | None = None
    bio: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    avatar_media_id: uuid.UUID | None = None
    member_status: MemberStatusLiteral | None = None
    availability: AvailabilityLiteral = "unavailable"
    years_experience: int | None = Field(default=None, ge=0, le=60)
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    visibility: VisibilityLiteral = "members"
    listed_in_directory: bool = False
    show_location: bool = True
    show_links: bool = True
    allow_contact: bool = False
    technologies: list[TechnologyIn] = []


class ProfileOut(BaseModel):
    user_id: uuid.UUID
    handle: str
    display_name: str
    title: str | None = None
    bio: str | None = None
    city: str | None = None
    country_code: str | None = None
    avatar_media_id: uuid.UUID | None = None
    member_status: str | None = None
    availability: str
    years_experience: int | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    visibility: str
    listed_in_directory: bool
    show_location: bool
    show_links: bool
    allow_contact: bool
    technologies: list[TechnologyOut] = []
    badges: list[BadgeOut] = []


class DirectoryItem(BaseModel):
    handle: str
    display_name: str
    title: str | None = None
    city: str | None = None
    country_code: str | None = None
    member_status: str | None = None
    avatar_media_id: uuid.UUID | None = None
    technologies: list[str] = []
    badges: list[str] = []


class PiiUpsert(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class PiiOut(BaseModel):
    user_id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class MemberContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    subject: str | None = None
    message: str = Field(min_length=1, max_length=5000)
    website: str | None = None


class DashboardItem(BaseModel):
    id: str
    kind: str
    title: str
    slug: str | None = None


class DashboardOut(BaseModel):
    events: list[DashboardItem]
    projects: list[DashboardItem]
    resources: list[DashboardItem]


class BadgeAward(BaseModel):
    code: str
    edition_year: int | None = None


class HideRequest(BaseModel):
    hidden: bool = True


class ApproveOut(BaseModel):
    user_id: uuid.UUID
    status: str
    approved_at: datetime | None


class MembersStatus(BaseModel):
    module: str = "members"
    status: str = "ready"
