"""Schémas Pydantic — programs."""

from pydantic import BaseModel


class ProgramsStatus(BaseModel):
    module: str = "programs"
    status: str = "not_implemented"
