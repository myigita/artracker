"""The startup schema check.

These build a database at the OLD schema on purpose — the rest of the suite
can't catch this class of bug, because conftest.py creates every table fresh
from the current models and so is never out of date.
"""
from sqlalchemy import create_engine, inspect, text

from app.database import ensure_schema
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
