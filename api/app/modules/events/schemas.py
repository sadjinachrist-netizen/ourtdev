"""Schémas Pydantic — événements (module 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EventTypeLiteral = Literal[
    "meetup", "workshop", "conference", "hackathon", "training", "festival", "other"
]
EventFormatLiteral = Literal["onsite", "online", "hybrid"]
ContentStatusLiteral = Literal["draft", "in_review", "published", "archived"]
WhenLiteral = Literal["upcoming", "past", "all"]
SpeakerRoleLiteral = Literal["speaker", "panelist", "moderator", "trainer"]
MediaKindLiteral = Literal["photo", "video"]
ParticipantRoleLiteral = Literal["attendee", "volunteer", "organizer"]


class TranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    title: str
    summary: str | None = None
    description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None


class SpeakerTranslationIn(BaseModel):
    language_code: str = Field(min_length=2, max_length=5)
    job_title: str | None = None
    bio: str | None = None


class EventCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=160)
    type: EventTypeLiteral
    format: EventFormatLiteral = "onsite"
    starts_at: datetime
    ends_at: datetime | None = None
    timezone: str = "Africa/Lome"
    venue: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    online_url: str | None = None
    registration_url: str | None = None
    replay_url: str | None = None
    cover_media_id: uuid.UUID | None = None
    community_id: int | None = None
    edition_year: int | None = None
    show_in_timeline: bool = False
    participants_count: int | None = Field(default=None, ge=0)
    sessions_count: int | None = Field(default=None, ge=0)
    show_stats: bool = False
    status: ContentStatusLiteral = "draft"
    published_at: datetime | None = None
    translations: list[TranslationIn] = Field(min_length=1)


class EventUpdate(BaseModel):
    type: EventTypeLiteral | None = None
    format: EventFormatLiteral | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    venue: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    online_url: str | None = None
    registration_url: str | None = None
    replay_url: str | None = None
    cover_media_id: uuid.UUID | None = None
    community_id: int | None = None
    edition_year: int | None = None
    show_in_timeline: bool | None = None
    participants_count: int | None = Field(default=None, ge=0)
    sessions_count: int | None = Field(default=None, ge=0)
    show_stats: bool | None = None
    status: ContentStatusLiteral | None = None
    published_at: datetime | None = None
    translations: list[TranslationIn] | None = None


class SpeakerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    organization: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    website_url: str | None = None
    user_id: uuid.UUID | None = None
    translations: list[SpeakerTranslationIn] = []


class EventSpeakerAttach(BaseModel):
    speaker_id: uuid.UUID
    role: SpeakerRoleLiteral = "speaker"
    position: int = 0


class EventMediaCreate(BaseModel):
    kind: MediaKindLiteral
    media_id: uuid.UUID | None = None
    url: str | None = None
    position: int = 0


class EventPartnerAttach(BaseModel):
    partner_id: uuid.UUID


class RegisterRequest(BaseModel):
    role: ParticipantRoleLiteral = "attendee"


class SpeakerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    website_url: str | None = None
    position: int = 0


class EventPartnerOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class EventMediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    media_id: uuid.UUID | None = None
    url: str | None = None
    position: int


class ResourceFolderLink(BaseModel):
    id: uuid.UUID
    slug: str


class EventListItem(BaseModel):
    id: uuid.UUID
    slug: str
    type: str
    format: str
    starts_at: datetime
    ends_at: datetime | None = None
    city: str | None = None
    venue: str | None = None
    language: str
    title: str
    summary: str | None = None
    show_in_timeline: bool = False


class EventOut(EventListItem):
    timezone: str
    country_code: str | None = None
    online_url: str | None = None
    registration_url: str | None = None
    replay_url: str | None = None
    description: str | None = None
    community_id: int | None = None
    edition_year: int | None = None
    status: str
    published_at: datetime | None = None
    show_stats: bool = False
    participants_count: int | None = None
    sessions_count: int | None = None
    speakers: list[SpeakerOut] = []
    partners: list[EventPartnerOut] = []
    gallery: list[EventMediaOut] = []
    resource_folder: ResourceFolderLink | None = None


class IdOut(BaseModel):
    id: uuid.UUID


class EventsStatus(BaseModel):
    module: str = "events"
    status: str = "ready"
