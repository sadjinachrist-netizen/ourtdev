"""Modèles SQLAlchemy — events (lecture lite pour l'accueil ; CRUD = module 3)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
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
    status: Mapped[ContentStatus] = mapped_column(
        content_status_enum, nullable=False, server_default=text("'draft'::content_status")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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

    event: Mapped[Event] = relationship(back_populates="translations")
