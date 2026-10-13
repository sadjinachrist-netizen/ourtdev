"""Modèles SQLAlchemy — bloc 6 (membres et annuaire)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MemberStatus(str, enum.Enum):
    student = "student"
    professional = "professional"
    freelance = "freelance"
    recruiter = "recruiter"
    other = "other"


class Availability(str, enum.Enum):
    available = "available"
    open = "open"
    unavailable = "unavailable"


class ProfileVisibility(str, enum.Enum):
    public = "public"
    members = "members"
    private = "private"


member_status_enum = ENUM(
    MemberStatus,
    name="member_status",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)
availability_enum = ENUM(
    Availability,
    name="availability",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)
profile_visibility_enum = ENUM(
    ProfileVisibility,
    name="profile_visibility",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)


class MemberProfile(Base):
    __tablename__ = "member_profiles"
    __table_args__ = (
        CheckConstraint("handle ~ '^[a-z0-9_-]{3,30}$'", name="member_profiles_handle_check"),
        CheckConstraint(
            "years_experience IS NULL OR years_experience BETWEEN 0 AND 60",
            name="member_profiles_years_experience_check",
        ),
        CheckConstraint(
            "NOT listed_in_directory OR directory_consent_at IS NOT NULL",
            name="member_profiles_directory_consent_check",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    handle: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    avatar_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    member_status: Mapped[MemberStatus | None] = mapped_column(member_status_enum)
    availability: Mapped[Availability] = mapped_column(
        availability_enum, nullable=False, server_default=text("'unavailable'::availability")
    )
    years_experience: Mapped[int | None] = mapped_column(SmallInteger)
    github_url: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    portfolio_url: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[ProfileVisibility] = mapped_column(
        profile_visibility_enum,
        nullable=False,
        server_default=text("'members'::profile_visibility"),
    )
    listed_in_directory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    directory_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    show_location: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_links: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    technologies: Mapped[list[MemberTechnology]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    badges: Mapped[list[MemberBadge]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class MemberPii(Base):
    __tablename__ = "member_pii"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Technology(Base):
    __tablename__ = "technologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(Text)


class MemberTechnology(Base):
    __tablename__ = "member_technologies"
    __table_args__ = (
        CheckConstraint("level IS NULL OR level BETWEEN 1 AND 5", name="member_technologies_level_check"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    technology_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("technologies.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int | None] = mapped_column(SmallInteger)

    profile: Mapped[MemberProfile] = relationship(back_populates="technologies")
    technology: Mapped[Technology] = relationship()


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    icon_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    translations: Mapped[list[BadgeTranslation]] = relationship(
        back_populates="badge", cascade="all, delete-orphan"
    )


class BadgeTranslation(Base):
    __tablename__ = "badge_translations"

    badge_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    badge: Mapped[Badge] = relationship(back_populates="translations")


class MemberBadge(Base):
    __tablename__ = "member_badges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("member_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    badge_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True
    )
    # FK réelle vers festival_editions : table non mappée dans ce module
    edition_year: Mapped[int | None] = mapped_column(SmallInteger)
    awarded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped[MemberProfile] = relationship(back_populates="badges")
    badge: Mapped[Badge] = relationship()


class MemberMessage(Base):
    __tablename__ = "member_messages"
    __table_args__ = (
        CheckConstraint("status IN ('sent', 'spam')", name="member_messages_status_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    sender_name: Mapped[str] = mapped_column(Text, nullable=False)
    sender_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'sent'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
