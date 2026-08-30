import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base

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
def ensure_schema(bind) -> None:
	inspector = inspect(bind)
	if "subjects" not in inspector.get_table_names():
		return

	columns = {column["name"] for column in inspector.get_columns("subjects")}
	if "category_id" not in columns:
		with bind.begin() as connection:
			connection.execute(
				text("ALTER TABLE subjects ADD COLUMN category_id INTEGER REFERENCES categories(id)")
			)


# Order matters: create_all first, so `categories` exists before anything points
# a foreign key at it.
Base.metadata.create_all(bind=engine)
ensure_schema(engine)