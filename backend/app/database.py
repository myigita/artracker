import os

from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from .models import PREDEFINED_PLATFORMS, Base, Platform, utcnow

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
	(
		"poll_schedule",
		"last_uid",
		("ALTER TABLE poll_schedule ADD COLUMN last_uid INTEGER",),
	),
	(
		"poll_schedule",
		"uid_validity",
		("ALTER TABLE poll_schedule ADD COLUMN uid_validity VARCHAR(255)",),
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


# The seed list itself lives in models.py, so Platform.is_preset can read it
# without importing this module. Deleting a seeded platform is refused outright
# — see delete_platform — rather than allowed and then silently undone here on
# the next restart.
def ensure_predefined_platforms(session: Session) -> None:
	"""Stage any missing built-in platforms in an existing transaction."""
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


def seed_platforms(bind) -> None:
	with Session(bind) as session:
		ensure_predefined_platforms(session)
		session.commit()


def migrate_handles_to_rules(bind) -> None:
	"""Carry retired subject handles across to per-tracker match rules.

	Handles could only ever find the artist in the sender's local part. Match rules
	replaced them because most platforms mail from a generic address and name the
	artist in the subject line instead. The old configuration still means
	something, though, so rather than dropping it: every handle becomes a
	"sender contains <handle>" rule on each of that subject's trackers.

	More permissive than the original — it matches anywhere in the address rather
	than the local part exactly — which is the safe direction. A rule that catches
	slightly too much is visible and editable; one that catches nothing looks like
	the artist went quiet.

	**At most one rule per tracker, even when the subject had several handles.**
	Handles were alternatives: any one of them identified the subject. A tracker's
	rules are ANDed, so turning three handles into three rules would demand a
	sender containing all three at once and match nothing at all — the exact
	silent failure this migration exists to avoid. The lowest handle alphabetically
	is taken for determinism, and any others are dropped; they're visible in the
	editor afterwards and easy to re-add as a broader rule.
	"""
	inspector = inspect(bind)
	if "subject_handles" not in inspector.get_table_names():
		return

	with bind.begin() as connection:
		pairs = connection.execute(
			text(
				"SELECT MIN(sh.handle), t.id FROM subject_handles sh"
				" JOIN trackers t ON t.subject_id = sh.subject_id"
				" GROUP BY t.id"
			)
		).fetchall()

		for handle, tracker_id in pairs:
			already = connection.execute(
				text(
					"SELECT 1 FROM match_rules WHERE tracker_id = :tracker"
					" AND field = 'sender' AND operator = 'contains' AND value = :value"
				),
				{"tracker": tracker_id, "value": handle},
			).first()
			if already:
				continue
			connection.execute(
				text(
					"INSERT INTO match_rules (tracker_id, field, operator, value, date_created)"
					" VALUES (:tracker, 'sender', 'contains', :value, :created)"
				),
				{"tracker": tracker_id, "value": handle, "created": utcnow()},
			)

		# Dropped rather than left behind, so the next boot is a no-op and nothing
		# reads a table the models no longer describe.
		connection.execute(text("DROP TABLE subject_handles"))


# Order matters: create_all first, so `categories` exists before anything points
# a foreign key at it, and `match_rules` exists before the handle migration writes
# into it. Then the column migrations, then seeding — which writes rows and
# therefore needs every column present already.
Base.metadata.create_all(bind=engine)
ensure_schema(engine)
migrate_handles_to_rules(engine)
seed_platforms(engine)
