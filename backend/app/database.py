import os

from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from .models import Base, Platform

# Relative path by default (resolves against the working directory), which keeps
# local dev unchanged. In Docker this is pointed at a mounted volume so the file
# survives container rebuilds — see DATABASE_URL in docker-compose.yml.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///artracker.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


# Columns added to tables that ALREADY EXIST, which create_all() will not do.
#
# create_all() creates missing *tables* and nothing else. When subjects.category_id
# was added, every database created before that point kept the old subjects table
# and 500d with "no such column" on every subject read — fixable only by running
# ALTER by hand on each deployed volume. This does it on startup instead.
#
# Each step checks before it acts, so this is a no-op on an up-to-date database
# and safe to run on every boot. It is not a substitute for real migrations: if
# this list grows much past one entry, or a change ever needs to rewrite data
# rather than just add a nullable column, switch to Alembic.
#
# Each entry is (table, column, statements-to-run-if-it-is-missing).
_MIGRATIONS: list[tuple[str, str, tuple[str, ...]]] = [
	(
		"subjects",
		"category_id",
		("ALTER TABLE subjects ADD COLUMN category_id INTEGER REFERENCES categories(id)",),
	),
	(
		# Two statements, because SQLite REFUSES to add a UNIQUE column via ALTER
		# TABLE — "Cannot add a UNIQUE column" — even though it will happily
		# enforce the same constraint through an index created afterwards. A
		# database built fresh by create_all() gets the constraint inline and
		# never reaches this path.
		"platforms",
		"mail_domain",
		(
			"ALTER TABLE platforms ADD COLUMN mail_domain VARCHAR(255)",
			"CREATE UNIQUE INDEX IF NOT EXISTS ix_platforms_mail_domain ON platforms (mail_domain)",
		),
	),
]


def ensure_schema(bind) -> None:
	inspector = inspect(bind)
	tables = set(inspector.get_table_names())

	for table, column, statements in _MIGRATIONS:
		if table not in tables:
			continue
		if column in {c["name"] for c in inspector.get_columns(table)}:
			continue
		with bind.begin() as connection:
			for statement in statements:
				connection.execute(text(statement))


# Platforms the app knows how to read notification mail for. Seeded rather than
# left to the user because the sender domain is a fact about the platform, not a
# preference — nobody should have to look up "creator.patreon.com" by hand.
#
# Deleting one puts it back on the next restart. That is the trade for not
# needing a "was this ever seeded" flag, and re-adding an empty platform row is
# cheap; the trackers hanging off it are what matter and they block the delete
# with a 409 anyway.
PREDEFINED_PLATFORMS: list[tuple[str, str]] = [
	("Patreon - Mail", "creator.patreon.com"),
]


def seed_platforms(bind) -> None:
	with Session(bind) as session:
		for name, mail_domain in PREDEFINED_PLATFORMS:
			# If ANY row already holds this domain, there is nothing to do — and
			# trying anyway is worse than useless. mail_domain is unique, this
			# function runs at import time, and an IntegrityError here doesn't fail
			# a request, it stops the app from starting at all. Found exactly that
			# way: a database seeded by an earlier version already had the domain
			# under a different name.
			if session.query(Platform).filter(Platform.mail_domain == mail_domain).first():
				continue

			# Case-insensitive on purpose. Someone who typed "patreon - mail" by
			# hand before this shipped would otherwise get a SECOND, near-identical
			# platform next to it — two rows that look the same in a dropdown, only
			# one of which actually reads mail. Matching loosely adopts theirs.
			platform = (
				session.query(Platform)
				.filter(func.lower(Platform.name) == name.lower())
				.first()
			)
			if platform is None:
				session.add(Platform(name=name, mail_domain=mail_domain))
			else:
				# Reached only when the domain is unclaimed, so this can't be
				# stealing it from anyone.
				platform.mail_domain = mail_domain
		session.commit()


# Order matters: create_all first, so `categories` exists before anything points
# a foreign key at it. Then the column migrations, then seeding — which writes
# rows and therefore needs every column to be present already.
Base.metadata.create_all(bind=engine)
ensure_schema(engine)
seed_platforms(engine)