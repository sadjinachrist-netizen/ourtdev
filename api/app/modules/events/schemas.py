"""Schémas Pydantic — events."""

from pydantic import BaseModel


class EventsStatus(BaseModel):
    module: str = "events"
    status: str = "not_implemented"
