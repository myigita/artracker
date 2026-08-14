from pydantic import BaseModel, Field, PlainSerializer
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

# Length limits live HERE, not in models.py. The `String(255)` columns look like
# constraints but SQLite ignores VARCHAR lengths entirely — a 100KB name was
# accepted happily before these were added. Pydantic is the only thing actually
# enforcing a bound, so don't remove these assuming the DB has your back.
#
# str_strip_whitespace makes "   " collapse to "" and then fail min_length,
# which is why whitespace-only names can't slip through either.
_STRICT = {"str_strip_whitespace": True}

Name = Annotated[str, Field(min_length=1, max_length=255)]
Url = Annotated[str, Field(min_length=1, max_length=2000)]
Description = Annotated[str, Field(max_length=1000)]


class SubjectIn(BaseModel):
    model_config = _STRICT

    name: Name

class SubjectOut(BaseModel):
    id: int
    name: str
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class PlatformIn(BaseModel):
    model_config = _STRICT

    name: Name

class PlatformOut(BaseModel):
    id: int
    name: str
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class TrackerIn(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    subject_name: Name
    platform_name: Name
    url: Url
    description: Description | None = None

class TrackerUpdate(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    url: Url | None = None
    description: Description | None = None

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