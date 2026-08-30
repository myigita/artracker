from pydantic import AfterValidator, AliasChoices, BaseModel, Field, PlainSerializer
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

# Serialized as "handles", but read from either name — and the ORDER is
# load-bearing.
#
# On an ORM object both attributes exist: `handles` is the relationship and holds
# SubjectHandle objects, while `handle_names` is the property that flattens them
# to strings. Trying "handles" first would find the relationship and fail
# validation against list[str]. Trying "handle_names" first gets the strings from
# a model, and falls through to "handles" for a JSON document — which is what
# lets one model serve export and import both.
_HANDLES = Field(
    default=[],
    validation_alias=AliasChoices("handle_names", "handles"),
    max_length=100,
)


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
    handles: list[Name] = _HANDLES

class SubjectUpdate(BaseModel):
    model_config = _STRICT

    # Still narrow — renaming would need 409 handling for the unique constraint
    # and is deliberately left out. Handles earn their place because mail
    # matching is useless without them and they change independently of the name.
    category_name: Name | None = None
    # An omitted key leaves handles alone; [] clears them. exclude_unset in the
    # route is what keeps those two apart.
    handles: list[Name] | None = Field(default=None, max_length=100)

class SubjectOut(BaseModel):
    id: int
    name: str
    category_name: str | None
    handles: list[str] = _HANDLES
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class PlatformIn(BaseModel):
    model_config = _STRICT

    name: Name
    # Set this and the platform becomes mail-trackable: incoming messages from
    # this sender domain resolve to its trackers. Null is a plain saved link.
    mail_domain: Name | None = None

class PlatformOut(BaseModel):
    id: int
    name: str
    mail_domain: str | None
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
    # Updates detected since last_checked. Computed on the model rather than
    # stored, so nothing can drift out of sync with the rows it counts.
    unread_count: int = 0

    model_config = {"from_attributes": True}


class UpdateOut(BaseModel):
    id: int
    tracker_id: int
    summary: str | None
    detected_at: UtcDatetime

    model_config = {"from_attributes": True}


class UnmatchedMailOut(BaseModel):
    id: int
    sender: str
    subject: str | None
    reason: str
    received_at: UtcDatetime

    model_config = {"from_attributes": True}


class PollResult(BaseModel):
    fetched: int
    recorded: int
    duplicates: int
    unmatched: int


# ---- Backup / restore ------------------------------------------------------
#
# Rows reference each other BY NAME, not by id. Names are already unique on all
# three lookup tables, the file stays readable, and it means the same document
# works for a merge into a database whose ids are completely different. Nothing
# outside the DB depends on the ids, so they're simply not exported.
#
# `updates` and `unmatched_mail` are deliberately NOT in the document. They are
# detected signals rather than things the user configured: re-polling the mailbox
# rebuilds them, they'd grow the file without bound, and their whole meaning is
# "newer than last_checked" — which a restore into a different database can't
# preserve anyway. Handles and mail domains ARE configuration and do get saved.

BACKUP_VERSION = 1

_FROM_ORM = {"from_attributes": True}


class CategoryBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    date_created: BackupDatetime | None = None


class PlatformBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    mail_domain: Name | None = None
    date_created: BackupDatetime | None = None


class SubjectBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    category_name: Name | None = None
    # Configuration, not derived data, so it has to survive a backup — without
    # this every export silently drops the handles and a restore leaves mail
    # matching resolving nothing.
    handles: list[Name] = _HANDLES
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