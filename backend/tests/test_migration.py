import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import ensure_schema, migrate_handles_to_rules, seed_platforms
from app.models import Base


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
	engine = create_engine(f"sqlite:///{tmp_path}/old.db")
	with engine.begin() as connection:
		connection.execute(text(OLD_SUBJECTS))
		connection.execute(
			text("INSERT INTO subjects (id, name, date_created) VALUES (1, 'Denji', '2026-01-01 00:00:00')")
		)
	return engine


def test_create_all_does_not_fix_an_existing_table(tmp_path):
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
	engine = create_engine(f"sqlite:///{tmp_path}/blank.db")

	ensure_schema(engine)

	assert inspect(engine).get_table_names() == []


OLD_POLL_SCHEDULE = """
CREATE TABLE poll_schedule (
	id INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	interval_minutes INTEGER NOT NULL,
	last_run_at DATETIME,
	last_result VARCHAR(500),
	PRIMARY KEY (id)
)
"""


def test_ensure_schema_adds_the_imap_uid_cursor(tmp_path):
	engine = create_engine(f"sqlite:///{tmp_path}/old-schedule.db")
	with engine.begin() as connection:
		connection.execute(text(OLD_POLL_SCHEDULE))
	Base.metadata.create_all(bind=engine)

	ensure_schema(engine)

	assert {"last_uid", "uid_validity"} <= columns_of(engine, "poll_schedule")

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
	engine = create_engine(f"sqlite:///{tmp_path}/old-platforms.db")
	with engine.begin() as connection:
		connection.execute(text(OLD_PLATFORMS))
		connection.execute(
			text("INSERT INTO platforms (id, name, date_created) VALUES (1, 'Pixiv', '2026-01-01 00:00:00')")
		)
	return engine


def test_sqlite_refuses_to_add_a_unique_column(tmp_path):
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


OLD_HANDLES = """
CREATE TABLE subject_handles (
	id INTEGER NOT NULL,
	subject_id INTEGER NOT NULL,
	handle VARCHAR(255) NOT NULL,
	date_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (handle)
)
"""


def database_with_handles(tmp_path):
	engine = create_engine(f"sqlite:///{tmp_path}/handles.db")
	Base.metadata.create_all(bind=engine)
	with engine.begin() as connection:
		connection.execute(text(OLD_HANDLES))
		connection.execute(text(
			"INSERT INTO subjects (id, name, date_created) VALUES (1, 'Pear', '2026-01-01 00:00:00')"
		))
		connection.execute(text(
			"INSERT INTO platforms (id, name, date_created) VALUES (1, 'Patreon - Mail', '2026-01-01 00:00:00')"
		))
		connection.execute(text(
			"INSERT INTO trackers (id, name, subject_id, platform_id, url, date_created)"
			" VALUES (1, 'Pear (Patreon - Mail)', 1, 1, '', '2026-01-01 00:00:00')"
		))
		connection.execute(text(
			"INSERT INTO subject_handles (id, subject_id, handle, date_created)"
			" VALUES (1, 1, 'peargor', '2026-01-01 00:00:00')"
		))
	return engine


def test_handles_become_match_rules(tmp_path):
	engine = database_with_handles(tmp_path)

	migrate_handles_to_rules(engine)

	with engine.begin() as connection:
		rules = connection.execute(
			text("SELECT tracker_id, field, operator, value FROM match_rules")
		).fetchall()
	assert rules == [(1, "sender", "contains", "peargor")]


def test_the_handles_table_is_dropped(tmp_path):
	engine = database_with_handles(tmp_path)

	migrate_handles_to_rules(engine)

	assert "subject_handles" not in inspect(engine).get_table_names()


def test_the_handle_migration_is_idempotent(tmp_path):
	engine = database_with_handles(tmp_path)

	migrate_handles_to_rules(engine)
	migrate_handles_to_rules(engine)

	with engine.begin() as connection:
		count = connection.execute(text("SELECT count(*) FROM match_rules")).scalar()
	assert count == 1


def test_a_handle_with_no_tracker_converts_to_nothing(tmp_path):
	engine = database_with_handles(tmp_path)
	with engine.begin() as connection:
		connection.execute(text("DELETE FROM trackers"))

	migrate_handles_to_rules(engine)

	with engine.begin() as connection:
		count = connection.execute(text("SELECT count(*) FROM match_rules")).scalar()
	assert count == 0


def test_the_handle_migration_is_a_noop_without_the_table(tmp_path):
	engine = create_engine(f"sqlite:///{tmp_path}/no-handles.db")
	Base.metadata.create_all(bind=engine)

	migrate_handles_to_rules(engine)  # must not raise


def test_several_handles_become_only_one_rule(tmp_path):
	engine = database_with_handles(tmp_path)
	with engine.begin() as connection:
		connection.execute(text(
			"INSERT INTO subject_handles (id, subject_id, handle, date_created)"
			" VALUES (2, 1, 'test213', '2026-01-01 00:00:00')"
		))

	migrate_handles_to_rules(engine)

	with engine.begin() as connection:
		rules = connection.execute(text("SELECT value FROM match_rules")).fetchall()
	assert rules == [("peargor",)]
