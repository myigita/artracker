import os

from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from .models import PREDEFINED_PLATFORMS, Base, Platform, utcnow

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///artracker.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


# Columns create_all() won't add to existing tables. Switch to Alembic if this grows.
_MIGRATIONS: list[tuple[str, str, tuple[str, ...]]] = [
	(
		"subjects",
		"category_id",
		("ALTER TABLE subjects ADD COLUMN category_id INTEGER REFERENCES categories(id)",),
	),
	(
		# SQLite can't ALTER in a UNIQUE column, so the constraint is a separate index.
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


def ensure_predefined_platforms(session: Session) -> None:
	for name, mail_domain in PREDEFINED_PLATFORMS:
		# Skip if any row owns the domain: an IntegrityError here would stop startup.
		if session.query(Platform).filter(Platform.mail_domain == mail_domain).first():
			continue

		# Case-insensitive, so a hand-made "patreon - mail" is adopted rather than duplicated.
		platform = (
			session.query(Platform)
			.filter(func.lower(Platform.name) == name.lower())
			.first()
		)
		if platform is None:
			session.add(Platform(name=name, mail_domain=mail_domain))
		else:
			platform.mail_domain = mail_domain


def seed_platforms(bind) -> None:
	with Session(bind) as session:
		ensure_predefined_platforms(session)
		session.commit()


def migrate_handles_to_rules(bind) -> None:
	# Retired subject handles become one "sender contains" rule per tracker (rules are ANDed).
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

		connection.execute(text("DROP TABLE subject_handles"))


# Order matters: tables, then columns, then data.
Base.metadata.create_all(bind=engine)
ensure_schema(engine)
migrate_handles_to_rules(engine)
seed_platforms(engine)
