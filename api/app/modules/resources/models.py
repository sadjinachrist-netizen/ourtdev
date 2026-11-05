"""Modèles SQLAlchemy — module 6 (ressources).
Alignés sur database/01_schema.sql (resource_folders, resources, resource_tags).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    DateTime,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import foreign

from app.core.database import Base


class ResourceType(str, enum.Enum):
    slides = "slides"
    video = "video"
    code = "code"
    link = "link"
    document = "document"


class AccessLevel(str, enum.Enum):
    public = "public"
    members = "members"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    published = "published"
    archived = "archived"


class ResourceFolder(Base):
    __tablename__ = "resource_folders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resource_folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs(id)", ondelete="SET NULL"), nullable=True
    )
    edition_year: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("festival_editions(year)", ondelete="SET NULL"), nullable=True
    )
    community_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("communities(id)", ondelete="SET NULL"), nullable=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        "access_level", nullable=False, server_default=text("'public'")
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[ContentStatus] = mapped_column(
        "content_status", nullable=False, server_default=text("'draft'")
    )
    published_at: Mapped[datetime | None] = mapped_column(
        "timestamptz", nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="resource_folders_no_self"),
    )

    parent: Mapped[ResourceFolder | None] = relationship(
        "ResourceFolder",
        foreign_keys="ResourceFolder.parent_id",
        remote_side="ResourceFolder.id",
        back_populates="children",
    )
    children: Mapped[list["ResourceFolder"]] = relationship(
        "ResourceFolder",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    translations: Mapped[list[ResourceFolderTranslation]] = relationship(
        "ResourceFolderTranslation", back_populates="folder", cascade="all, delete-orphan"
    )
    resources: Mapped[list[Resource]] = relationship(
        "Resource",
        back_populates="folder",
        cascade="all, delete-orphan",
        primaryjoin="foreign(Resource.folder_id) == ResourceFolder.id",
    )


class ResourceFolderTranslation(Base):
    __tablename__ = "resource_folder_translations"

    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource_folders.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    folder: Mapped[ResourceFolder] = relationship(back_populates="translations")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource_folders(id)", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[ResourceType] = mapped_column("resource_type", nullable=False)
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files(id)", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str | None] = mapped_column(Text)
    speaker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True
    )
    access_level: Mapped[AccessLevel] = mapped_column(
        "access_level", nullable=False, server_default=text("'public'")
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[ContentStatus] = mapped_column(
        "content_status", nullable=False, server_default=text("'draft'")
    )
    published_at: Mapped[datetime | None] = mapped_column(
        "timestamptz", nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    translations: Mapped[list[ResourceTranslation]] = relationship(
        "ResourceTranslation",
        back_populates="resource",
        cascade="all, delete-orphan",
        primaryjoin="ResourceTranslation.resource_id == Resource.id",
    )
    tags: Mapped[list[ResourceTag]] = relationship(
        "ResourceTag", back_populates="resource", cascade="all, delete-orphan"
    )

    folder: Mapped[ResourceFolder] = relationship(
        back_populates="resources",
        foreign_keys="Resource.folder_id",
        primaryjoin="Resource.folder_id == ResourceFolder.id",
    )


class ResourceTranslation(Base):
    __tablename__ = "resource_translations"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources(id)", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    resource: Mapped[Resource] = relationship(back_populates="translations")


class ResourceTag(Base):
    __tablename__ = "resource_tags"

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources(id)", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags(id)", ondelete="CASCADE"), primary_key=True
    )

    resource: Mapped[Resource] = relationship(back_populates="tags")


Index("ix_resource_folders_parent_slug", "parent_id", "slug")
Index("ix_resource_folders_event", "event_id")
Index("ix_resource_folder_translations_folder_id", "folder_id")
Index("ix_resources_folder_position", "folder_id", "position")
Index("ix_resources_folder", "folder_id")
Index("ix_resources_type_access_status", "type", "access_level", "status")
Index("ix_resource_translations_resource_id", "resource_id")
