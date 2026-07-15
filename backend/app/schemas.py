from pydantic import BaseModel, PlainSerializer
from datetime import datetime, timezone
from typing import Annotated


def _serialize_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_serialize_utc, return_type=str, when_used="json"),
]

class SubjectIn(BaseModel):
    name: str

class SubjectOut(BaseModel):
    id: int
    name: str
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class PlatformIn(BaseModel):
    name: str

class PlatformOut(BaseModel):
    id: int
    name: str
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class TrackerIn(BaseModel):
    name: str | None = None
    subject_name: str
    platform_name: str
    url: str
    description: str | None = None

class TrackerOut(BaseModel):
    id: int
    name: str
    subject_name: str
    platform_name: str
    url: str
    description: str | None
    date_created: UtcDatetime
    last_checked: UtcDatetime | None

    model_config = {"from_attributes": True}