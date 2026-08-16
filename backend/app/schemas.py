from pydantic import AfterValidator, BaseModel, Field, PlainSerializer
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated


def _serialize_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


UtcDatetime = Annotated[
    datetime,
    PlainSerializer(_serialize_utc, return_type=str, when_used="json"),
]


def _to_naive_utc(dt: datetime) -> datetime:
    """Inbound counterpart to UtcDatetime.

    The DB holds naive UTC, so an aware datetime arriving on the wire has to be
    converted *and* stripped. Leaving it to SQLite is not an option: it discards
    tzinfo without converting, so "18:00+03:00" would land as 18:00 UTC — three
    hours in the future rather than the same instant.
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


NaiveUtcDatetime = Annotated[datetime, AfterValidator(_to_naive_utc)]

# A backup document is both written and read, so its timestamps need BOTH
# directions: parsed down to naive UTC coming in, re-marked as UTC going out.
# That's what lets one set of models serve export and import.
BackupDatetime = Annotated[
    datetime,
    AfterValidator(_to_naive_utc),
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


class CategoryIn(BaseModel):
    model_config = _STRICT

    name: Name

class CategoryOut(BaseModel):
    id: int
    name: str
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class SubjectIn(BaseModel):
    model_config = _STRICT

    name: Name
    category_name: Name | None = None

class SubjectUpdate(BaseModel):
    model_config = _STRICT

    # Deliberately narrow: assigning a category is the only thing this exists
    # for. Renaming a subject would need 409 handling for the unique constraint
    # — add it when it's actually wanted.
    category_name: Name | None = None

class SubjectOut(BaseModel):
    id: int
    name: str
    category_name: str | None
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
    # Writable so the UI can undo an accidental check. null is a real value
    # here — it restores a tracker that had never been checked before.
    last_checked: NaiveUtcDatetime | None = None

class TrackerOut(BaseModel):
    id: int
    name: str
    subject_name: str
    subject_category: str | None
    platform_name: str
    url: str
    description: str | None
    date_created: UtcDatetime
    last_checked: UtcDatetime | None

    model_config = {"from_attributes": True}


# ---- Backup / restore ------------------------------------------------------
#
# Rows reference each other BY NAME, not by id. Names are already unique on all
# three lookup tables, the file stays readable, and it means the same document
# works for a merge into a database whose ids are completely different. Nothing
# outside the DB depends on the ids, so they're simply not exported.

BACKUP_VERSION = 1

_FROM_ORM = {"from_attributes": True}


class CategoryBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    date_created: BackupDatetime | None = None


class PlatformBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    date_created: BackupDatetime | None = None


class SubjectBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    category_name: Name | None = None
    date_created: BackupDatetime | None = None


class TrackerBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    subject_name: Name
    platform_name: Name
    url: Url
    description: Description | None = None
    date_created: BackupDatetime | None = None
    last_checked: BackupDatetime | None = None


class Backup(BaseModel):
    model_config = _FROM_ORM

    version: int = BACKUP_VERSION
    exported_at: BackupDatetime | None = None
    categories: list[CategoryBackup] = []
    platforms: list[PlatformBackup] = []
    subjects: list[SubjectBackup] = []
    trackers: list[TrackerBackup] = []


class ImportMode(str, Enum):
    # Add what's missing, leave everything already here alone.
    merge = "merge"
    # Wipe first, then restore the file exactly. A real "restore from backup".
    replace = "replace"


class ImportResult(BaseModel):
    mode: ImportMode
    categories_added: int
    platforms_added: int
    subjects_added: int
    trackers_added: int
    skipped: int
    deleted: int