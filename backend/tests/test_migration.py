"""The startup schema check.

These build a database at the OLD schema on purpose — the rest of the suite
can't catch this class of bug, because conftest.py creates every table fresh
from the current models and so is never out of date.
"""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import ensure_schema, seed_platforms
from app.models import Base


# subjects exactly as it was before categories existed.
OLD_SUBJECTS = """
CREATE TABLE subjects (
	id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	date_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)
"""


def columns_of(engine, table):
	return {column["name"] for column in inspect(engine).get_columns(table)}


def old_database(tmp_path):
	"""A file database stuck at the pre-categories schema, with a row in it."""
	engine = create_engine(f"sqlite:///{tmp_path}/old.db")
	with engine.begin() as connection:
		connection.execute(text(OLD_SUBJECTS))
		connection.execute(
			text("INSERT INTO subjects (id, name, date_created) VALUES (1, 'Denji', '2026-01-01 00:00:00')")
		)
	return engine


def test_create_all_does_not_fix_an_existing_table(tmp_path):
	"""The premise. If this ever fails, the startup check is unnecessary."""
	engine = old_database(tmp_path)

	Base.metadata.create_all(bind=engine)

	assert "categories" in inspect(engine).get_table_names()  # new table: created
	assert "category_id" not in columns_of(engine, "subjects")  # new column: not


def test_ensure_schema_adds_the_missing_column(tmp_path):
	engine = old_database(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	assert "category_id" in columns_of(engine, "subjects")


def test_existing_rows_survive_and_default_to_no_category(tmp_path):
	engine = old_database(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	with engine.begin() as connection:
		rows = connection.execute(text("SELECT name, category_id FROM subjects")).fetchall()
	assert rows == [("Denji", None)]


def test_running_twice_does_not_raise(tmp_path):
	"""Every boot calls this, so a second run must not hit "duplicate column"."""
	engine = old_database(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)
	ensure_schema(engine)

	assert "category_id" in columns_of(engine, "subjects")


def test_noop_on_a_current_database(tmp_path):
	engine = create_engine(f"sqlite:///{tmp_path}/new.db")
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	assert "category_id" in columns_of(engine, "subjects")


def test_noop_on_an_empty_database(tmp_path):
	"""No tables at all — must not blow up before create_all has ever run."""
	engine = create_engine(f"sqlite:///{tmp_path}/blank.db")

	ensure_schema(engine)

	assert inspect(engine).get_table_names() == []

# platforms exactly as it was before notification mail existed.
OLD_PLATFORMS = """
CREATE TABLE platforms (
	id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	date_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)
"""


def old_platforms(tmp_path):
	"""A file database whose platforms table predates mail_domain."""
	engine = create_engine(f"sqlite:///{tmp_path}/old-platforms.db")
	with engine.begin() as connection:
		connection.execute(text(OLD_PLATFORMS))
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (1, 'Pixiv', '2026-01-01 00:00:00')")
		)
	return engine


def test_sqlite_refuses_to_add_a_unique_column(tmp_path):
	"""The premise for why this migration is two statements instead of one.

	If SQLite ever allows it, the CREATE UNIQUE INDEX step becomes redundant.
	"""
	engine = old_platforms(tmp_path)

	with pytest.raises(OperationalError):
		with engine.begin() as connection:
			connection.execute(
				text("ALTER TABLE platforms ADD COLUMN probe VARCHAR(255) UNIQUE")
			)


def test_ensure_schema_adds_mail_domain(tmp_path):
	engine = old_platforms(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	assert "mail_domain" in columns_of(engine, "platforms")


def test_existing_platforms_survive_with_no_domain(tmp_path):
	engine = old_platforms(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	with engine.begin() as connection:
		rows = connection.execute(text("SELECT name, mail_domain FROM platforms")).fetchall()
	assert rows == [("Pixiv", None)]


def test_the_index_really_enforces_uniqueness(tmp_path):
	"""Adding the column is only half of it — the constraint has to arrive too."""
	engine = old_platforms(tmp_path)
	Base.metadata.create_all(bind=engine)
	ensure_schema(engine)

	with engine.begin() as connection:
		connection.execute(text("UPDATE platforms SET mail_domain = 'creator.patreon.com'"))
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (2, 'Other', '2026-01-01 00:00:00')")
		)

	with pytest.raises(IntegrityError):
		with engine.begin() as connection:
			connection.execute(
				text("UPDATE platforms SET mail_domain = 'creator.patreon.com' WHERE id = 2")
			)


def test_many_platforms_can_have_no_domain(tmp_path):
	"""Load-bearing: every link-only platform leaves mail_domain NULL, and SQLite
	permits any number of NULLs in a unique column."""
	engine = old_platforms(tmp_path)
	Base.metadata.create_all(bind=engine)
	ensure_schema(engine)

	with engine.begin() as connection:
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (2, 'Bluesky', '2026-01-01 00:00:00')")
		)
		count = connection.execute(
			text("SELECT count(*) FROM platforms WHERE mail_domain IS NULL")
		).scalar()
	assert count == 2


def test_platform_migration_runs_twice_without_raising(tmp_path):
	engine = old_platforms(tmp_path)
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)
	ensure_schema(engine)

	assert "mail_domain" in columns_of(engine, "platforms")


def test_seeding_creates_the_predefined_platforms(tmp_path):
	engine = create_engine(f"sqlite:///{tmp_path}/seed.db")
	Base.metadata.create_all(bind=engine)

	seed_platforms(engine)

	with engine.begin() as connection:
		rows = connection.execute(text("SELECT name, mail_domain FROM platforms")).fetchall()
	assert ("Patreon - Mail", "creator.patreon.com") in rows


def test_seeding_twice_does_not_duplicate(tmp_path):
	"""It runs on every boot, so it has to be idempotent."""
	engine = create_engine(f"sqlite:///{tmp_path}/seed-twice.db")
	Base.metadata.create_all(bind=engine)

	seed_platforms(engine)
	seed_platforms(engine)

	with engine.begin() as connection:
		count = connection.execute(
			text("SELECT count(*) FROM platforms WHERE name = 'Patreon - Mail'")
		).scalar()
	assert count == 1


def test_seeding_backfills_a_domain_onto_a_hand_made_platform(tmp_path):
	"""Someone who created "Patreon - Mail" by hand before this feature shipped
	should end up with a working one, not a dead duplicate."""
	engine = create_engine(f"sqlite:///{tmp_path}/seed-backfill.db")
	Base.metadata.create_all(bind=engine)
	with engine.begin() as connection:
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (1, 'Patreon - Mail', '2026-01-01 00:00:00')")
		)

	seed_platforms(engine)

	with engine.begin() as connection:
		rows = connection.execute(text("SELECT id, mail_domain FROM platforms")).fetchall()
	assert rows == [(1, "creator.patreon.com")]


def test_seeding_adopts_a_differently_cased_existing_platform(tmp_path):
	"""Regression, found against the real database: someone had typed
	"patreon - mail" by hand, and an exact-name match seeded a second
	"Patreon - Mail" beside it — two rows that look identical in a dropdown,
	only one of which reads mail."""
	engine = create_engine(f"sqlite:///{tmp_path}/seed-case.db")
	Base.metadata.create_all(bind=engine)
	with engine.begin() as connection:
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (1, 'patreon - mail', '2026-01-01 00:00:00')")
		)

	seed_platforms(engine)

	with engine.begin() as connection:
		rows = connection.execute(text("SELECT name, mail_domain FROM platforms")).fetchall()
	assert rows == [("patreon - mail", "creator.patreon.com")]


def test_seeding_leaves_an_already_claimed_domain_alone(tmp_path):
	"""Regression, and a boot-breaker: seed_platforms runs at import time, so an
	IntegrityError here stops the app starting rather than failing one request.

	The real database reached this state — a row seeded under "Patreon - Mail"
	alongside a hand-typed "patreon - mail". A case-insensitive name lookup finds
	the hand-typed one first and would try to give it a domain the other already
	holds.
	"""
	engine = create_engine(f"sqlite:///{tmp_path}/seed-claimed.db")
	Base.metadata.create_all(bind=engine)
	with engine.begin() as connection:
		connection.execute(
			text("INSERT INTO platforms (id, name, mail_domain, date_created)"
			     " VALUES (1, 'patreon - mail', NULL, '2026-01-01 00:00:00')")
		)
		connection.execute(
			text("INSERT INTO platforms (id, name, mail_domain, date_created)"
			     " VALUES (2, 'Patreon - Mail', 'creator.patreon.com', '2026-01-01 00:00:00')")
		)

	seed_platforms(engine)  # must not raise

	with engine.begin() as connection:
		rows = connection.execute(
			text("SELECT id, mail_domain FROM platforms ORDER BY id")
		).fetchall()
	assert rows == [(1, None), (2, "creator.patreon.com")]
