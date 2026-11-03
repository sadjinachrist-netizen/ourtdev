"""Modèles SQLAlchemy — bloc 2 (contenus) + key_figures."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContentStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    published = "published"
    archived = "archived"


content_status_enum = ENUM(
    ContentStatus,
    name="content_status",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    status: Mapped[ContentStatus] = mapped_column(
        content_status_enum, nullable=False, server_default=text("'draft'::content_status")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    translations: Mapped[list[PageTranslation]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class PageTranslation(Base):
    __tablename__ = "page_translations"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    meta_title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)

    page: Mapped[Page] = relationship(back_populates="translations")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        CheckConstraint("team_group IN ('board', 'team')", name="team_members_team_group_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    photo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    team_group: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'team'"))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    translations: Mapped[list[TeamMemberTranslation]] = relationship(
        back_populates="team_member", cascade="all, delete-orphan"
    )


class TeamMemberTranslation(Base):
    __tablename__ = "team_member_translations"

    team_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("team_members.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    role_title: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)

    team_member: Mapped[TeamMember] = relationship(back_populates="translations")


class PartnerLevel(Base):
    __tablename__ = "partner_levels"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    translations: Mapped[list[PartnerLevelTranslation]] = relationship(
        back_populates="level", cascade="all, delete-orphan"
    )
    partners: Mapped[list[Partner]] = relationship(back_populates="level")


class PartnerLevelTranslation(Base):
    __tablename__ = "partner_level_translations"

    level_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("partner_levels.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    level: Mapped[PartnerLevel] = relationship(back_populates="translations")


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    logo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    website_url: Mapped[str | None] = mapped_column(Text)
    level_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("partner_levels.id", ondelete="SET NULL")
    )
    show_on_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    level: Mapped[PartnerLevel | None] = relationship(back_populates="partners")
    translations: Mapped[list[PartnerTranslation]] = relationship(
        back_populates="partner", cascade="all, delete-orphan"
    )


class PartnerTranslation(Base):
    __tablename__ = "partner_translations"

    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text)

    partner: Mapped[Partner] = relationship(back_populates="translations")


class ArticleCategory(Base):
    __tablename__ = "article_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    translations: Mapped[list[ArticleCategoryTranslation]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class ArticleCategoryTranslation(Base):
    __tablename__ = "article_category_translations"

    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("article_categories.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[ArticleCategory] = relationship(back_populates="translations")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("article_categories.id", ondelete="SET NULL")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    status: Mapped[ContentStatus] = mapped_column(
        content_status_enum, nullable=False, server_default=text("'draft'::content_status")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    translations: Mapped[list[ArticleTranslation]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(secondary="article_tags")


class ArticleTranslation(Base):
    __tablename__ = "article_translations"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    meta_title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)

    article: Mapped[Article] = relationship(back_populates="translations")


class ArticleTag(Base):
    __tablename__ = "article_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'read', 'handled', 'spam')",
            name="contact_messages_status_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str | None] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    handled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KeyFigure(Base):
    __tablename__ = "key_figures"
    __table_args__ = (
        CheckConstraint(
            "edition_year IS NULL OR program_id IS NULL",
            name="key_figures_edition_or_program_check",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    suffix: Mapped[str | None] = mapped_column(Text)
    # FK DB vers festival_editions / programs — tables mappées dans modules 4 et 7
    edition_year: Mapped[int | None] = mapped_column(SmallInteger)
    program_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    show_on_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    translations: Mapped[list[KeyFigureTranslation]] = relationship(
        back_populates="key_figure", cascade="all, delete-orphan"
    )


class KeyFigureTranslation(Base):
    __tablename__ = "key_figure_translations"

    key_figure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("key_figures.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)

    key_figure: Mapped[KeyFigure] = relationship(back_populates="translations")
