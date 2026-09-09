from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)

# Handles are matched against the local part of an email sender, and email local
# parts are not case-sensitive in practice — "PearGor" and "peargor" are the same
# creator. Normalising on write AND on lookup is what stops them becoming two
# rows that can never both match.
def normalize_handle(handle: str) -> str:
	return handle.strip().lower()

# Platforms the app ships knowing how to read mail for. Lives here rather than in
# database.py so the Platform model can consult it without importing the module
# that imports it — database.py already depends on this one.
#
# The sender domain is a fact about the platform, not a preference; nobody should
# have to look up "creator.patreon.com" by hand.
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

	# delete-orphan because handles are OWNED by their subject — deleting the
	# subject should take them with it. That's the opposite of trackers, which are
	# peers and block the delete with a 409 instead. SQLite has foreign keys
	# disabled, so this cascade is enforced by SQLAlchemy in Python and by nothing
	# else; without it, deleting a subject strands its handle rows and they keep
	# matching incoming mail against a subject that no longer exists.
	handles: Mapped[list["SubjectHandle"]] = relationship(
		back_populates="subject", cascade="all, delete-orphan"
	)

	@property
	def category_name(self) -> str | None:
		return self.category.name if self.category else None

	@property
	def handle_names(self) -> list[str]:
		return sorted(h.handle for h in self.handles)

class SubjectHandle(Base):
	"""What a subject is called on some platform — e.g. `peargor` on Patreon.

	Kept out of `Subject.name` so the name can stay human-readable while the
	handles stay machine-matchable, and because one artist has a different handle
	on every platform they post to.
	"""
	__tablename__ = "subject_handles"

	id: Mapped[int] = mapped_column(primary_key=True)

	subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
	subject: Mapped["Subject"] = relationship(back_populates="handles")

	# Unique across ALL subjects, not merely within one. A handle has to resolve
	# to exactly one subject or mail matching needs a tie-breaking rule, and there
	# is no good one. If two artists ever genuinely share a handle on different
	# platforms, that is the point to add platform_id here — not before.
	handle: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Platform(Base):
	__tablename__ = "platforms"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
	trackers: Mapped[list["Tracker"]] = relationship(back_populates="platform")

	# The sender domain of this platform's notification email, e.g.
	# "creator.patreon.com". Null means the platform is a plain saved link with no
	# automatic updates, which is every platform that existed before this feature.
	#
	# Unique so two platforms can't claim the same domain and make a match
	# ambiguous. SQLite permits any number of NULLs in a unique column, so all the
	# link-only platforms coexist happily.
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

	# Owned children, same reasoning as Subject.handles: an update is meaningless
	# without the tracker it belongs to.
	updates: Mapped[list["Update"]] = relationship(
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

	# The source's own identifier for this event — a Message-ID for mail, a post
	# id for an API source later. Unique, and that uniqueness is the entire
	# mechanism that makes re-polling the same mailbox idempotent.
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