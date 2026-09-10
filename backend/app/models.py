from datetime import datetime, timezone
from sqlalchemy import Boolean, String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)

# Platforms the app ships knowing about. Lives here rather than in database.py so
# the Platform model can consult it without importing the module that imports it
# — database.py already depends on this one.
#
# The sender domain is a fact about the platform, not a preference; nobody should
# have to look up "creator.patreon.com" by hand. It no longer drives matching —
# it seeds a starting match rule when a tracker is created on the platform.
PREDEFINED_PLATFORMS: list[tuple[str, str]] = [
	("Patreon - Mail", "creator.patreon.com"),
]

_PRESET_NAMES = {name.lower() for name, _ in PREDEFINED_PLATFORMS}

class Base(DeclarativeBase):
	pass

class Category(Base):
	__tablename__ = "categories"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
	subjects: Mapped[list["Subject"]] = relationship(back_populates="category")

class Subject(Base):
	__tablename__ = "subjects"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
	trackers: Mapped[list["Tracker"]] = relationship(back_populates="subject")

	# Optional: subjects predate categories, and there's no sensible default to
	# backfill. `Mapped[int | None]` is what makes the column nullable — SQLAlchemy
	# 2.0 reads nullability off the annotation.
	category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
	category: Mapped["Category | None"] = relationship(back_populates="subjects")

	@property
	def category_name(self) -> str | None:
		return self.category.name if self.category else None

class Platform(Base):
	__tablename__ = "platforms"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
	trackers: Mapped[list["Tracker"]] = relationship(back_populates="platform")

	# The sender domain of this platform's notification email, e.g.
	# "creator.patreon.com". No longer used for matching — it is a convenience that
	# seeds a first match rule when a tracker is created here, so you don't have to
	# look the domain up. Null means the platform has no known notification mail.
	mail_domain: Mapped[str | None] = mapped_column(String(255), unique=True)

	# Seeded platforms are refused deletion. Deleting one used to "work" and then
	# have it reappear on the next restart, which reads as the app ignoring you.
	# Derived from the seed list rather than stored, so there's no column to fall
	# out of step with it and no migration to add one.
	@property
	def is_preset(self) -> bool:
		return self.name is not None and self.name.lower() in _PRESET_NAMES

class Tracker(Base):
	__tablename__ = "trackers"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)
	description: Mapped[str] = mapped_column(String(255), nullable=True)

	subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
	subject: Mapped["Subject"] = relationship(back_populates="trackers")

	platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
	platform: Mapped["Platform"] = relationship(back_populates="trackers")

	url: Mapped[str] = mapped_column(String(255), nullable=False)
	last_checked: Mapped[datetime] = mapped_column(DateTime, nullable=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

	# Owned children: an update is meaningless without the tracker it belongs to,
	# and a rule without one has nothing to match against.
	updates: Mapped[list["Update"]] = relationship(
		back_populates="tracker", cascade="all, delete-orphan"
	)
	rules: Mapped[list["MatchRule"]] = relationship(
		back_populates="tracker", cascade="all, delete-orphan"
	)

	@property
	def subject_name(self) -> str:
		return self.subject.name

	@property
	def platform_name(self) -> str:
		return self.platform.name

	# Two hops (tracker -> subject -> category), so this is the one property here
	# that can be None: a subject doesn't have to be categorized.
	@property
	def subject_category(self) -> str | None:
		return self.subject.category_name

	# Updates detected since the last time this tracker was opened. Reusing
	# last_checked rather than storing a separate "last seen" means clicking Open
	# clears the badge for free, and the existing undo un-clears it.
	@property
	def unread_count(self) -> int:
		if self.last_checked is None:
			return len(self.updates)
		return sum(1 for update in self.updates if update.detected_at > self.last_checked)

class MatchRule(Base):
	"""One condition an incoming message must satisfy to land on this tracker.

	Replaces the earlier scheme of subject handles plus a per-platform sender
	domain. That could only find the artist in the sender's local part —
	`peargor@creator.patreon.com` — which is how Patreon happens to work and how
	most platforms don't. They mail from one generic address and put the artist in
	the subject line, which the old model had no way to express at all.

	A rule belongs to a tracker rather than a subject because it is inherently
	about one artist on one platform, and that pair IS a tracker. It also drops
	the constraint handles needed: they had to be globally unique so a handle
	resolved to exactly one subject, since there was no sensible tie-breaker.
	"""
	__tablename__ = "match_rules"

	id: Mapped[int] = mapped_column(primary_key=True)

	tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id"), nullable=False)
	tracker: Mapped["Tracker"] = relationship(back_populates="rules")

	# "sender" or "subject". Validated by the schema rather than a DB enum, which
	# is how the other string columns here work. The message body is deliberately
	# not an option yet: headers are already in hand after a fetch, whereas bodies
	# mean parsing multipart HTML and are where false positives live.
	field: Mapped[str] = mapped_column(String(32), nullable=False)
	# contains / not_contains / equals / not_equals.
	operator: Mapped[str] = mapped_column(String(32), nullable=False)
	value: Mapped[str] = mapped_column(String(500), nullable=False)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Update(Base):
	"""One detected "they posted something" event, from any source.

	Deliberately source-agnostic: the email poller writes these today, and a
	Bluesky or Danbooru poller would write the same rows tomorrow with no change
	to the badge that reads them.
	"""
	__tablename__ = "updates"

	id: Mapped[int] = mapped_column(primary_key=True)

	tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id"), nullable=False)
	tracker: Mapped["Tracker"] = relationship(back_populates="updates")

	# The source's identifier for this event, SCOPED TO THE TRACKER — the poller
	# stores "<tracker id>:<Message-ID>". One message can satisfy several trackers'
	# rules now, and each needs its own row, so a bare Message-ID would collide
	# with itself on this unique index. Prefixing keeps re-polling idempotent per
	# tracker without rebuilding the table to relax the constraint, which SQLite
	# cannot do in place.
	external_ref: Mapped[str] = mapped_column(String(998), nullable=False, unique=True)
	summary: Mapped[str] = mapped_column(String(1000), nullable=True)
	detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class MailAccount(Base):
	"""The gathering mailbox's credentials. At most one row, always id 1.

	A single row rather than a key/value settings table because these five fields
	are only ever read and written together, and a table with one row is easier to
	reason about than five loose strings.

	**The password is write-only above this layer.** No response model exposes it,
	the backup document doesn't carry it, and the only way to change it is to send
	a new one. That matters more here than in most apps: every endpoint is
	unauthenticated, so a field that leaks into a GET is a field served to anyone
	who can reach the container.

	It is still plaintext at rest. Encrypting it would mean storing the key beside
	the database, which protects against nothing real — the honest mitigation is a
	dedicated mailbox that receives only forwarded notifications, so the worst case
	is losing that account rather than a real one.
	"""
	__tablename__ = "mail_account"

	id: Mapped[int] = mapped_column(primary_key=True)
	host: Mapped[str] = mapped_column(String(255), nullable=False)
	port: Mapped[int] = mapped_column(default=993)
	username: Mapped[str] = mapped_column(String(320), nullable=False)
	password: Mapped[str] = mapped_column(String(1000), nullable=False)
	mailbox: Mapped[str] = mapped_column(String(255), default="INBOX")
	updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class PollSchedule(Base):
	"""When the background poller should run. One row, always id 1.

	Separate from MailAccount rather than a column on it, because the mailbox can
	come from the environment instead — and then there is no MailAccount row to
	hang a schedule off. The two are independent settings that happen to concern
	the same feature.

	`last_run_at` is what makes the schedule survive a restart: the loop asks
	whether a run is *due* rather than sleeping for the interval, so changing the
	interval takes effect on the next tick instead of after the current sleep, and
	a restart doesn't reset the clock.
	"""
	__tablename__ = "poll_schedule"

	id: Mapped[int] = mapped_column(primary_key=True)
	# Off until switched on. A background process that starts reaching out to a
	# mail server the moment the container boots is not a good default.
	enabled: Mapped[bool] = mapped_column(Boolean, default=False)
	interval_minutes: Mapped[int] = mapped_column(default=15)
	last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
	# A one-line summary of the last pass, or the error it failed with. Without it
	# a background poller is completely opaque — there is no request to watch fail.
	last_result: Mapped[str] = mapped_column(String(500), nullable=True)

class UnmatchedMail(Base):
	"""Mail that looked like a notification but resolved to no tracker.

	This exists because the alternative is silent failure. Sender addresses and
	subject formats change without notice, and a poller that quietly drops what it
	can't parse looks identical to a platform that simply went quiet. Keeping the
	rejects visible turns "no updates for three weeks" into something diagnosable.
	"""
	__tablename__ = "unmatched_mail"

	id: Mapped[int] = mapped_column(primary_key=True)

	external_ref: Mapped[str] = mapped_column(String(998), nullable=False, unique=True)
	sender: Mapped[str] = mapped_column(String(320), nullable=False)
	subject: Mapped[str] = mapped_column(String(1000), nullable=True)
	# Which step of the resolution failed: unknown domain, unknown handle, or no
	# tracker joining the two. Without it you can see that mail was rejected but
	# not what to fix.
	reason: Mapped[str] = mapped_column(String(255), nullable=False)
	received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)