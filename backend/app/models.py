from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
	pass

class Artist(Base):
	__tablename__ = "artists"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
	trackers: Mapped[list["Tracker"]] = relationship(back_populates="artist")

class Platform(Base):
	__tablename__ = "platforms"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
	trackers: Mapped[list["Tracker"]] = relationship(back_populates="platform")

class Tracker(Base):
	__tablename__ = "trackers"

	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False)

	artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), nullable=False)
	artist: Mapped["Artist"] = relationship(back_populates="trackers")

	platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
	platform: Mapped["Platform"] = relationship(back_populates="trackers")

	url: Mapped[str] = mapped_column(String(255), nullable=False)
	last_checked: Mapped[datetime] = mapped_column(DateTime, nullable=True)
	date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)