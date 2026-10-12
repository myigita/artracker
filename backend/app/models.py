from datetime import datetime, timezone
from sqlalchemy import Boolean, String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)

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

	mail_domain: Mapped[str | None] = mapped_column(String(255), unique=True)

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

	@property
	def subject_category(self) -> str | None:
		return self.subject.category_name

	@property
	def unread_count(self) -> int:
		if self.last_checked is None:
			return len(self.updates)
		return sum(1 for update in self.updates if update.detected_at > self.last_checked)

class MatchRule(Base):
	__tablename__ = "match_rules"

	id: Mapped[int] = mapped_column(primary_key=True)

	tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id"), nullable=False)
	tracker: Mapped["Tracker"] = relationship(back_populates="rules")

	field: Mapped[str] = mapped_column(String(32), nullable=False)
	operator: Mapped[str] = mapped_column(String(32), nullable=False)
	value: Mapped[str] = mapped_column(String(500), nullable=False)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Update(Base):
	__tablename__ = "updates"

	id: Mapped[int] = mapped_column(primary_key=True)

	tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id"), nullable=False)
	tracker: Mapped["Tracker"] = relationship(back_populates="updates")

	# "<tracker id>:<Message-ID>": one message can match several trackers.
	external_ref: Mapped[str] = mapped_column(String(998), nullable=False, unique=True)
	summary: Mapped[str] = mapped_column(String(1000), nullable=True)
	detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class MailAccount(Base):
	# Single row. The password must never be exposed by a response model.
	__tablename__ = "mail_account"

	id: Mapped[int] = mapped_column(primary_key=True)
	host: Mapped[str] = mapped_column(String(255), nullable=False)
	port: Mapped[int] = mapped_column(default=993)
	username: Mapped[str] = mapped_column(String(320), nullable=False)
	password: Mapped[str] = mapped_column(String(1000), nullable=False)
	mailbox: Mapped[str] = mapped_column(String(255), default="INBOX")
	updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class PollSchedule(Base):
	__tablename__ = "poll_schedule"

	id: Mapped[int] = mapped_column(primary_key=True)
	enabled: Mapped[bool] = mapped_column(Boolean, default=False)
	interval_minutes: Mapped[int] = mapped_column(default=15)
	last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
	last_result: Mapped[str] = mapped_column(String(500), nullable=True)
	# Cursor over IMAP UIDs; reset when UIDVALIDITY changes.
	last_uid: Mapped[int | None] = mapped_column(nullable=True)
	uid_validity: Mapped[str | None] = mapped_column(String(255), nullable=True)

class UnmatchedMail(Base):
	__tablename__ = "unmatched_mail"

	id: Mapped[int] = mapped_column(primary_key=True)

	external_ref: Mapped[str] = mapped_column(String(998), nullable=False, unique=True)
	sender: Mapped[str] = mapped_column(String(320), nullable=False)
	subject: Mapped[str] = mapped_column(String(1000), nullable=True)
	reason: Mapped[str] = mapped_column(String(255), nullable=False)
	received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
