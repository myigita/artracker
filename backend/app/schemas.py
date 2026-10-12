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
    # SQLite drops tzinfo without converting, so convert before stripping.
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


NaiveUtcDatetime = Annotated[datetime, AfterValidator(_to_naive_utc)]

BackupDatetime = Annotated[
    datetime,
    AfterValidator(_to_naive_utc),
    PlainSerializer(_serialize_utc, return_type=str, when_used="json"),
]

# SQLite ignores VARCHAR lengths, so these limits are the only bound.
_STRICT = {"str_strip_whitespace": True}

Name = Annotated[str, Field(min_length=1, max_length=255)]
Url = Annotated[str, Field(min_length=1, max_length=2000)]
Description = Annotated[str, Field(max_length=1000)]

# Allows "": whether a tracker needs a URL is decided in the route.
BlankableUrl = Annotated[str, Field(max_length=2000)]

class MatchField(str, Enum):
    sender = "sender"
    subject = "subject"


class MatchOperator(str, Enum):
    contains = "contains"
    not_contains = "not_contains"
    equals = "equals"
    not_equals = "not_equals"


class MatchRuleIn(BaseModel):
    model_config = {**_STRICT, "from_attributes": True}

    field: MatchField
    operator: MatchOperator
    value: Annotated[str, Field(min_length=1, max_length=500)]


class MatchRuleOut(BaseModel):
    id: int
    field: str
    operator: str
    value: str

    model_config = {"from_attributes": True}


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
    mail_domain: Name | None = None

class PlatformOut(BaseModel):
    id: int
    name: str
    mail_domain: str | None
    is_preset: bool
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class TrackerIn(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    subject_name: Name
    platform_name: Name
    url: BlankableUrl | None = None
    description: Description | None = None
    rules: list[MatchRuleIn] | None = Field(default=None, max_length=25)

class TrackerUpdate(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    url: BlankableUrl | None = None
    description: Description | None = None
    rules: list[MatchRuleIn] | None = Field(default=None, max_length=25)
    # null is valid: undoing a first check restores "never".
    last_checked: NaiveUtcDatetime | None = None

class TrackerOut(BaseModel):
    id: int
    name: str
    subject_name: str
    subject_category: str | None
    platform_name: str
    url: str
    description: str | None
    rules: list[MatchRuleOut] = []
    date_created: UtcDatetime
    last_checked: UtcDatetime | None
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


class PollScheduleIn(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(default=15, ge=5, le=1440)


class PollScheduleOut(BaseModel):
    enabled: bool
    interval_minutes: int
    last_run_at: UtcDatetime | None
    last_result: str | None
    next_run_at: UtcDatetime | None

    model_config = {"from_attributes": True}


class MailAccountIn(BaseModel):
    model_config = _STRICT

    host: Name
    port: int = Field(default=993, ge=1, le=65535)
    username: Name
    # Omitted keeps the stored password.
    password: str | None = Field(default=None, min_length=1, max_length=1000)
    mailbox: Name = "INBOX"


class MailAccountOut(BaseModel):
    # Never add the password here.
    host: str
    port: int
    username: str
    mailbox: str
    has_password: bool
    source: str


# Backup rows reference each other by name, not id. Updates and unmatched mail aren't exported.

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
    date_created: BackupDatetime | None = None


class TrackerBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    subject_name: Name
    platform_name: Name
    url: BlankableUrl = ""
    description: Description | None = None
    rules: list[MatchRuleIn] = []
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
    merge = "merge"
    replace = "replace"


class ImportResult(BaseModel):
    mode: ImportMode
    categories_added: int
    platforms_added: int
    subjects_added: int
    trackers_added: int
    skipped: int
    deleted: int
