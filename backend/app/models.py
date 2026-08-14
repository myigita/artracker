from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)

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