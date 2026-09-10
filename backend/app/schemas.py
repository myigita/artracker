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

# Same as Url but permits "". Whether a tracker may go without one depends on its
# platform, which Pydantic can't see — so blank has to reach the route rather than
# being rejected here as a 422. With min_length on it, clearing a URL was
# impossible and a blank one failed with a schema error instead of the actual
# reason.
BlankableUrl = Annotated[str, Field(max_length=2000)]

class MatchField(str, Enum):
    sender = "sender"
    # The message body is deliberately absent. Headers are already in hand after a
    # fetch; bodies mean parsing multipart HTML and are where false positives live.
    # The model takes another value without a schema change when it's wanted.
    subject = "subject"


class MatchOperator(str, Enum):
    contains = "contains"
    # The negative forms are what make a broad sender rule usable — "from Patreon
    # but not the weekly digest".
    not_contains = "not_contains"
    equals = "equals"
    not_equals = "not_equals"


class MatchRuleIn(BaseModel):
    # from_attributes so the backup export can build these straight off the ORM
    # rows, which is what lets one model serve both directions the way the other
    # backup models do.
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

    # Deliberately narrow: assigning a category is all this exists for. Renaming
    # would need 409 handling for the unique constraint — add it when wanted.
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
    # A convenience, not a matching rule: a tracker created on this platform gets
    # a starting "sender contains <domain>" rule so you don't have to look it up.
    mail_domain: Name | None = None

class PlatformOut(BaseModel):
    id: int
    name: str
    mail_domain: str | None
    # Seeded by the app and refused deletion. Sent so the UI can disable the
    # control rather than offering a button that always fails.
    is_preset: bool
    date_created: UtcDatetime

    model_config = {"from_attributes": True}

class TrackerIn(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    subject_name: Name
    platform_name: Name
    # A tracker needs a URL or at least one match rule — the route enforces that.
    # URL only is a manual bookmark; rules only is a mail-watched artist with no
    # page; both is the useful case, so neither is required on its own.
    url: BlankableUrl | None = None
    description: Description | None = None
    # Omitted falls back to the platform's mail_domain, if it has one.
    rules: list[MatchRuleIn] | None = Field(default=None, max_length=25)

class TrackerUpdate(BaseModel):
    model_config = _STRICT

    name: Name | None = None
    # Blank is meaningful: it clears the URL, which the route allows only when
    # the tracker still has rules to work from.
    url: BlankableUrl | None = None
    description: Description | None = None
    # Replaced wholesale, like handles were. An omitted key leaves the rules
    # alone; [] clears them, which the route refuses when there is no URL to fall
    # back on — that would leave a tracker that does nothing at all.
    rules: list[MatchRuleIn] | None = Field(default=None, max_length=25)
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
    rules: list[MatchRuleOut] = []
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


class MailAccountIn(BaseModel):
    model_config = _STRICT

    host: Name
    port: int = Field(default=993, ge=1, le=65535)
    username: Name
    # Optional so the form can be re-saved without retyping the password — the
    # UI never receives it back, so it has nothing to send unless the user is
    # actually changing it. Omitted means "keep what's stored"; an empty string
    # is rejected rather than silently wiping the credential.
    password: str | None = Field(default=None, min_length=1, max_length=1000)
    mailbox: Name = "INBOX"


class MailAccountOut(BaseModel):
    """Everything about the mailbox EXCEPT the password.

    The omission is the point. Every endpoint here is unauthenticated, so a
    password on a response model is a password served to anyone who can reach the
    app. `has_password` carries the only thing the UI actually needs to know.
    """
    host: str
    port: int
    username: str
    mailbox: str
    has_password: bool
    # "database", "environment" or "unset" — so the Settings page can say where
    # the current mailbox came from instead of showing a form that looks empty
    # on a container configured through env vars.
    source: str


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
    date_created: BackupDatetime | None = None


class TrackerBackup(BaseModel):
    model_config = _FROM_ORM

    name: Name
    subject_name: Name
    platform_name: Name
    url: BlankableUrl = ""
    description: Description | None = None
    # Configuration, not derived data, so it has to survive a backup — without
    # this an export silently drops every rule and a restore leaves mail matching
    # nothing at all.
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