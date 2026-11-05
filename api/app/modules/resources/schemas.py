"""Schémas Pydantic v2 — module 6 (ressources).

Champs communs aux ressources (fichier ou lien).
"""
from enum import Enum

from pydantic import BaseModel


class ResourceType(str, Enum):
    slides = "slides"
    video = "video"
    code = "code"
    link = "link"
    document = "document"


class AccessLevel(str, Enum):
    public = "public"
    members = "members"


class ContentStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    published = "published"
    archived = "archived"


class ResourceOut(BaseModel):
    id: str
    folder_id: str
    type: ResourceType
    title: str | None
    description: str | None
    access_level: AccessLevel
    view_count: int
    download_count: int
    status: ContentStatus
    published_at: str | None
    media_id: str | None
    url: str | None
    speaker_id: str | None


class ResourceFolderOut(BaseModel):
    id: str
    slug: str
    parent_id: str | None
    path: list[str]
    event_id: str | None
    program_id: str | None
    edition_year: int | None
    access_level: AccessLevel
    status: ContentStatus
    published_at: str | None
    child_count: int
    resource_count: int
    translated_name: str | None


class ResourcesStatus(BaseModel):
    module: str = "resources"
    status: str = "ready"
