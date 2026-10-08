from pydantic import BaseModel, Field


class Message(BaseModel):
    detail: str
    code: str = "ok"


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    version: str
    env: str
