"""Modèles SQLAlchemy — événements et intervenants (module 3)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.contents.models import ContentStatus, content_status_enum


class EventType(str, enum.Enum):
    meetup = "meetup"
    workshop = "workshop"
    conference = "conference"
    hackathon = "hackathon"
    training = "training"
    festival = "festival"
    other = "other"


class EventFormat(str, enum.Enum):
    onsite = "onsite"
    online = "online"
    hybrid = "hybrid"


event_type_enum = ENUM(
    EventType,
    name="event_type",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)
event_format_enum = ENUM(
    EventFormat,
    name="event_format",
    create_type=False,
    values_callable=lambda x: [e.value for e in x],
)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[EventType] = mapped_column(event_type_enum, nullable=False)
    format: Mapped[EventFormat] = mapped_column(
        event_format_enum, nullable=False, server_default=text("'onsite'::event_format")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Africa/Lome'"))
    venue: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2))
    online_url: Mapped[str | None] = mapped_column(Text)
    registration_url: Mapped[str | None] = mapped_column(Text)
    replay_url: Mapped[str | None] = mapped_column(Text)
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    # communities et festival_editions ne sont pas mappées ici : pas de ForeignKey
    community_id: Mapped[int | None] = mapped_column(Integer)
    edition_year: Mapped[int | None] = mapped_column(SmallInteger)
    show_in_timeline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    participants_count: Mapped[int | None] = mapped_column(Integer)
    sessions_count: Mapped[int | None] = mapped_column(Integer)
    show_stats: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    translations: Mapped[list[EventTranslation]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventTranslation(Base):
    __tablename__ = "event_translations"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    meta_title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)

    event: Mapped[Event] = relationship(back_populates="translations")


class EventMedia(Base):
    __tablename__ = "event_media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="CASCADE")
    )
    url: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    photo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="SET NULL")
    )
    organization: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    github_url: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    translations: Mapped[list[SpeakerTranslation]] = relationship(
        back_populates="speaker", cascade="all, delete-orphan"
    )


class SpeakerTranslation(Base):
    __tablename__ = "speaker_translations"

    speaker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="CASCADE"), primary_key=True
    )
    language_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("languages.code", ondelete="CASCADE"), primary_key=True
    )
    job_title: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)

    speaker: Mapped[Speaker] = relationship(back_populates="translations")


class EventSpeaker(Base):
    __tablename__ = "event_speakers"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    speaker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="speaker")
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class EventPartner(Base):
    __tablename__ = "event_partners"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id", ondelete="CASCADE"), primary_key=True
    )


class EventParticipant(Base):
    __tablename__ = "event_participants"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="attendee")
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
