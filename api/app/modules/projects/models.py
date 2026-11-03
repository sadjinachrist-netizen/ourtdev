"""Modèles SQLAlchemy — projects (module 5). Alignés sur database/01_schema.sql."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectStage(str, enum.Enum):
    idea = "idea"
    in_progress = "in_progress"
    maintained = "maintained"
    archived = "archived"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


project_stage_enum = Enum(ProjectStage, name="project_stage", create_type=False)
review_status_enum = Enum(ReviewStatus, name="review_status", create_type=False)


class ProjectCategory(Base):
    __tablename__ = "project_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    translations: Mapped[list[ProjectCategoryTranslation]] = relationship(
        "ProjectCategoryTranslation", back_populates="category", cascade="all, delete-orphan"
    )

    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="category", cascade="all, delete-orphan"
    )


class ProjectCategoryTranslation(Base):
    __tablename__ = "project_category_translations"

    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_categories.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[ProjectCategory] = relationship(back_populates="translations")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("project_categories.id", ondelete="SET NULL")
    )
    stage: Mapped[ProjectStage] = mapped_column(
        project_stage_enum, nullable=False, server_default=text("'idea'::project_stage")
    )
    license: Mapped[str | None] = mapped_column(Text)
    repo_url: Mapped[str | None] = mapped_column(Text)
    demo_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        review_status_enum,
        nullable=False,
        server_default=text("'pending'::review_status"),
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    github_full_name: Mapped[str | None] = mapped_column(Text, unique=True)
    github_stars: Mapped[int | None] = mapped_column(Integer)
    github_forks: Mapped[int | None] = mapped_column(Integer)
    github_contributors_count: Mapped[int | None] = mapped_column(Integer)
    github_last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    github_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "review_status <> 'rejected' OR rejection_reason IS NOT NULL",
            name="projects_review_check",
        ),
    )

    category: Mapped[ProjectCategory | None] = relationship(
        "ProjectCategory", back_populates="projects"
    )
    translations: Mapped[list[ProjectTranslation]] = relationship(
        "ProjectTranslation", back_populates="project", cascade="all, delete-orphan"
    )
    technologies: Mapped[list[ProjectTechnology]] = relationship(
        "ProjectTechnology", back_populates="project", cascade="all, delete-orphan"
    )
    contributors: Mapped[list[ProjectContributor]] = relationship(
        "ProjectContributor", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectTranslation(Base):
    __tablename__ = "project_translations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="translations")


class ProjectTechnology(Base):
    __tablename__ = "project_technologies"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    technology_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technologies.id", ondelete="CASCADE"), primary_key=True
    )

    project: Mapped[Project] = relationship(back_populates="technologies")
    technology: Mapped[Any] = relationship()

Index("ix_project_technologies_project_id", "project_id")


class ProjectContributor(Base):
    __tablename__ = "project_contributors"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        Text, nullable=False, default="contributor", server_default=text("'contributor'")
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="contributors")
    user: Mapped[Any] = relationship()

Index("ix_project_contributors_project_id", "project_id")
