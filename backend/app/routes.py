from datetime import timedelta

from fastapi import APIRouter, HTTPException, Depends

from .database import ensure_predefined_platforms, get_db
from .mail import (
	MailError,
	get_mail_config,
	get_mail_fetcher,
	mail_config_from_env,
	record_batch,
)
from .models import (
	Category,
	MailAccount,
	MatchRule,
	PollSchedule,
	Subject,
	Tracker,
	Platform,
	UnmatchedMail,
	Update,
	utcnow,
)
from .schemas import (
	TrackerIn,
	TrackerOut,
	TrackerUpdate,
	SubjectIn,
	SubjectOut,
	SubjectUpdate,
	PlatformIn,
	PlatformOut,
	CategoryIn,
	CategoryOut,
	Backup,
	BACKUP_VERSION,
	CategoryBackup,
	PlatformBackup,
	SubjectBackup,
	TrackerBackup,
	ImportMode,
	ImportResult,
	MailAccountIn,
	MailAccountOut,
	MatchRuleIn,
	PollResult,
	PollScheduleIn,
	PollScheduleOut,
	UnmatchedMailOut,
	UpdateOut,
)
from sqlalchemy.orm import Session, joinedload, selectinload

router = APIRouter(prefix="/api/trackers")
subjects_router = APIRouter(prefix="/api/subjects")
platforms_router = APIRouter(prefix="/api/platforms")
categories_router = APIRouter(prefix="/api/categories")
backup_router = APIRouter(prefix="/api/backup")
mail_router = APIRouter(prefix="/api/mail")

@router.get("/", response_model=list[TrackerOut])
def get_trackers(db: Session = Depends(get_db)):
	# selectinload for updates specifically: unread_count walks the collection on
	# every row, so without it a list of N trackers costs N extra queries.
	trackers = (
		db.query(Tracker)
		.options(selectinload(Tracker.updates), selectinload(Tracker.rules))
		# populate_existing because this endpoint's whole job is to report current
		# state. Without it a Tracker already in the session's identity map keeps
		# whatever collections it loaded earlier, so unread_count can be computed
		# from a stale `updates` list — a poll adds rows and the badge stays at
		# zero. Invisible in production, where every request gets a new session,
		# and very visible in tests, which share one.
		.populate_existing()
		.order_by(Tracker.date_created.desc())
		.all()
	)
	return trackers

@router.get("/{tracker_id}", response_model=TrackerOut)
def get_tracker(tracker_id: int, db: Session = Depends(get_db)):
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
	if tracker:
		return tracker
	raise HTTPException(status_code=404, detail="Tracker not found")

@router.post("/", response_model=TrackerOut, status_code=201)
def create_tracker(tracker_in: TrackerIn, db: Session = Depends(get_db)):
	subject = db.query(Subject).filter(Subject.name == tracker_in.subject_name).first()
	if not subject:
		raise HTTPException(status_code=400, detail="Invalid subject")

	platform = db.query(Platform).filter(Platform.name == tracker_in.platform_name).first()
	if not platform:
		raise HTTPException(status_code=400, detail="Invalid platform")

	url = (tracker_in.url or "").strip()

	# A platform domain is shared by all its artists. Treating it as a default rule
	# makes every notification on that platform land on every tracker, so omitted
	# rules now mean exactly what they say: no rules.
	rules_in = tracker_in.rules or []

	name = tracker_in.name if tracker_in.name else f"{tracker_in.subject_name} ({tracker_in.platform_name})"

	tracker = Tracker(
		name=name,
		subject=subject,
		platform=platform,
		# Empty string rather than NULL. The column is NOT NULL, and SQLite can't
		# drop that without rebuilding the table — while setting nullable=True on
		# the model alone would work on a fresh database and raise IntegrityError
		# on every migrated one, which the test suite could never catch because
		# conftest builds its tables from the current models every run.
		url=url,
		description=tracker_in.description
	)
	_set_rules(tracker, rules_in)
	_require_url_or_rules(url, tracker.rules, name)

	db.add(tracker)
	db.commit()
	return tracker

@router.patch("/{tracker_id}", response_model=TrackerOut)
def update_tracker(tracker_id: int, tracker_update: TrackerUpdate, db: Session = Depends(get_db)):
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
	if not tracker:
		raise HTTPException(status_code=404, detail="Tracker not found")

	# exclude_unset keeps "field omitted" distinct from "field set to null":
	# only keys the client actually sent end up here.
	changes = tracker_update.model_dump(exclude_unset=True)

	# Pydantic's min_length already rejects "" and whitespace, but an explicit
	# JSON null passes it (the fields are Optional) and would write NULL into a
	# NOT NULL column — a 500. These turn that into a 400. description and
	# last_checked are excluded on purpose: both columns are nullable, and
	# nulling them is meaningful — clearing a description, and undoing a check
	# on a tracker that had never been checked before.
	if "name" in changes and not changes["name"]:
		raise HTTPException(status_code=400, detail="Name cannot be empty")
	# A null would hit the NOT NULL column, so a cleared URL lands as "".
	if "url" in changes and not changes["url"]:
		changes["url"] = ""

	# Rules come out before the generic setattr loop below: model_dump has already
	# turned them into plain dicts, and assigning those to the relationship would
	# fail. The parsed models are still on tracker_update.
	rules_sent = "rules" in changes
	changes.pop("rules", None)

	# Validated against what the tracker WOULD become, and before anything is
	# applied. Clearing the URL is fine if rules remain and clearing the rules is
	# fine if a URL remains, but not both — and a rejection has to leave the object
	# untouched rather than trusting that the session is discarded unread.
	prospective_url = (changes["url"] if "url" in changes else tracker.url) or ""
	prospective_rules = (
		[rule for rule in (tracker_update.rules or []) if rule.value.strip()]
		if rules_sent
		else tracker.rules
	)
	_require_url_or_rules(prospective_url.strip(), prospective_rules, tracker.name)

	if rules_sent:
		_set_rules(tracker, tracker_update.rules or [])

	for field, value in changes.items():
		setattr(tracker, field, value)

	db.commit()
	return tracker

@router.get("/{tracker_id}/updates", response_model=list[UpdateOut])
def get_tracker_updates(tracker_id: int, db: Session = Depends(get_db)):
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
	if not tracker:
		raise HTTPException(status_code=404, detail="Tracker not found")

	return (
		db.query(Update)
		.filter(Update.tracker_id == tracker_id)
		.order_by(Update.detected_at.desc())
		.all()
	)

@router.post("/{tracker_id}/check", response_model=TrackerOut)
def check_tracker(tracker_id: int, db: Session = Depends(get_db)):
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
	if not tracker:
		raise HTTPException(status_code=404, detail="Tracker not found")

	tracker.last_checked = utcnow()
	db.commit()
	return tracker

@router.delete("/{tracker_id}", response_model=TrackerOut)
def delete_tracker(tracker_id: int, db: Session = Depends(get_db)):
	# The children are loaded, and refreshed, on purpose: delete-orphan cascades
	# over the collections as SQLAlchemy currently holds them. If the session
	# already cached an empty `updates` — which happens whenever rows were added
	# by tracker_id rather than by appending — the cascade finds nothing and
	# leaves orphans behind, still holding their unique external_ref and blocking
	# the same mail from ever being recorded again.
	tracker = (
		db.query(Tracker)
		.options(selectinload(Tracker.updates), selectinload(Tracker.rules))
		.populate_existing()
		.filter(Tracker.id == tracker_id)
		.first()
	)
	if not tracker:
		raise HTTPException(status_code=404, detail="Tracker not found")

	db.delete(tracker)
	db.commit()
	return tracker

# Same contract as the subject/platform lookups in create_tracker: categories are
# referenced by name and must already exist — no auto-create.
def _lookup_category(name: str, db: Session) -> Category:
	category = db.query(Category).filter(Category.name == name).first()
	if not category:
		raise HTTPException(status_code=400, detail="Invalid category")
	return category

# Replaces a tracker's rules wholesale, the way the PATCH body describes them.
# Mutated in place rather than reassigned: assigning a fresh list makes SQLAlchemy
# delete every row and insert every row with no guaranteed ordering, which bit the
# handles version when a value was re-sent unchanged.
def _set_rules(tracker: Tracker, rules: list[MatchRuleIn]) -> None:
	# De-duplicated as it's built, not just filtered. Two identical rules in one
	# request are a slip rather than a conflict, and appending both would store the
	# same condition twice — the second can never change any outcome.
	wanted: list[tuple[str, str, str]] = []
	for rule in rules:
		value = rule.value.strip()
		if not value:
			continue
		key = (rule.field.value, rule.operator.value, value)
		if key not in wanted:
			wanted.append(key)

	existing = {(r.field, r.operator, r.value): r for r in tracker.rules}

	for key, row in existing.items():
		if key not in wanted:
			tracker.rules.remove(row)

	for field, operator, value in wanted:
		if (field, operator, value) not in existing:
			tracker.rules.append(MatchRule(field=field, operator=operator, value=value))


# A tracker that has neither a link to open nor a rule to catch mail does nothing
# at all, so one of the two is required. Which one is up to the user.
def _require_url_or_rules(url: str, rules: list, name: str) -> None:
	if not url and not rules:
		raise HTTPException(
			status_code=400,
			detail=f"'{name}' needs a URL or at least one match rule",
		)

	# Negative rules can only narrow a positive match. On their own, a rule such as
	# "subject doesn't contain digest" accepts almost every message in the mailbox.
	if rules and not any(rule.operator in ("contains", "equals") for rule in rules):
		raise HTTPException(
			status_code=400,
			detail=f"'{name}' needs at least one positive contains or equals rule",
		)


@subjects_router.get("/", response_model=list[SubjectOut])
def get_subjects(db: Session = Depends(get_db)):
	return db.query(Subject).order_by(Subject.name).all()

@subjects_router.post("/", response_model=SubjectOut, status_code=201)
def create_subject(subject_in: SubjectIn, db: Session = Depends(get_db)):
	existing = db.query(Subject).filter(Subject.name == subject_in.name).first()
	if existing:
		raise HTTPException(status_code=409, detail="Subject already exists")

	category = None
	if subject_in.category_name:
		category = _lookup_category(subject_in.category_name, db)

	subject = Subject(name=subject_in.name, category=category)
	db.add(subject)
	db.commit()
	return subject

@subjects_router.patch("/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, subject_update: SubjectUpdate, db: Session = Depends(get_db)):
	subject = db.query(Subject).filter(Subject.id == subject_id).first()
	if not subject:
		raise HTTPException(status_code=404, detail="Subject not found")

	changes = subject_update.model_dump(exclude_unset=True)

	# Unlike the tracker PATCH, an explicit null is *valid* here: category_id is
	# nullable, so sending null is how you clear a subject's category. Omitting
	# the key entirely leaves it alone — that's what exclude_unset buys us.
	if "category_name" in changes:
		name = changes["category_name"]
		subject.category = _lookup_category(name, db) if name else None

	db.commit()
	return subject

@subjects_router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
	subject = db.query(Subject).filter(Subject.id == subject_id).first()
	if not subject:
		raise HTTPException(status_code=404, detail="Subject not found")

	tracker_count = db.query(Tracker).filter(Tracker.subject_id == subject_id).count()
	if tracker_count:
		raise HTTPException(
			status_code=409,
			detail=f"Subject still has {tracker_count} tracker(s); delete those first",
		)

	db.delete(subject)
	db.commit()

@platforms_router.get("/", response_model=list[PlatformOut])
def get_platforms(db: Session = Depends(get_db)):
	return db.query(Platform).order_by(Platform.name).all()

@platforms_router.post("/", response_model=PlatformOut, status_code=201)
def create_platform(platform_in: PlatformIn, db: Session = Depends(get_db)):
	existing = db.query(Platform).filter(Platform.name == platform_in.name).first()
	if existing:
		raise HTTPException(status_code=409, detail="Platform already exists")

	mail_domain = platform_in.mail_domain.lower() if platform_in.mail_domain else None
	if mail_domain:
		# Two platforms claiming one domain makes every message from it ambiguous,
		# so the constraint is real. Checked here to return a 409 rather than let
		# the unique index raise an IntegrityError as a 500.
		clash = db.query(Platform).filter(Platform.mail_domain == mail_domain).first()
		if clash:
			raise HTTPException(
				status_code=409,
				detail=f"Domain '{mail_domain}' already belongs to '{clash.name}'",
			)

	platform = Platform(name=platform_in.name, mail_domain=mail_domain)
	db.add(platform)
	db.commit()
	return platform

@platforms_router.delete("/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
	platform = db.query(Platform).filter(Platform.id == platform_id).first()
	if not platform:
		raise HTTPException(status_code=404, detail="Platform not found")

	# Seeding recreates these on every boot, so allowing the delete meant the row
	# vanished and then came back — indistinguishable from the app ignoring you.
	# Refusing outright at least says what's happening.
	if platform.is_preset:
		raise HTTPException(
			status_code=409,
			detail=f"'{platform.name}' is built in and can't be deleted",
		)

	tracker_count = db.query(Tracker).filter(Tracker.platform_id == platform_id).count()
	if tracker_count:
		raise HTTPException(
			status_code=409,
			detail=f"Platform still has {tracker_count} tracker(s); delete those first",
		)

	db.delete(platform)
	db.commit()

@categories_router.get("/", response_model=list[CategoryOut])
def get_categories(db: Session = Depends(get_db)):
	return db.query(Category).order_by(Category.name).all()

@categories_router.post("/", response_model=CategoryOut, status_code=201)
def create_category(category_in: CategoryIn, db: Session = Depends(get_db)):
	existing = db.query(Category).filter(Category.name == category_in.name).first()
	if existing:
		raise HTTPException(status_code=409, detail="Category already exists")

	category = Category(name=category_in.name)
	db.add(category)
	db.commit()
	return category

@categories_router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
	category = db.query(Category).filter(Category.id == category_id).first()
	if not category:
		raise HTTPException(status_code=404, detail="Category not found")

	# Counts subjects, not trackers — this is the only thing standing in for the
	# foreign key SQLite isn't enforcing. Without it, deleting a category leaves
	# subjects pointing at an id that no longer exists, and category_name blows up.
	subject_count = db.query(Subject).filter(Subject.category_id == category_id).count()
	if subject_count:
		raise HTTPException(
			status_code=409,
			detail=f"Category still has {subject_count} subject(s); reassign those first",
		)

	db.delete(category)
	db.commit()

@backup_router.get("/export", response_model=Backup)
def export_backup(db: Session = Depends(get_db)):
	return Backup(
		version=BACKUP_VERSION,
		exported_at=utcnow(),
		categories=[CategoryBackup.model_validate(c) for c in db.query(Category).order_by(Category.name)],
		platforms=[PlatformBackup.model_validate(p) for p in db.query(Platform).order_by(Platform.name)],
		subjects=[SubjectBackup.model_validate(s) for s in db.query(Subject).order_by(Subject.name)],
		trackers=[TrackerBackup.model_validate(t) for t in db.query(Tracker).order_by(Tracker.date_created)],
	)

@backup_router.post("/import", response_model=ImportResult)
def import_backup(
	payload: Backup,
	mode: ImportMode = ImportMode.merge,
	db: Session = Depends(get_db),
):
	if payload.version != BACKUP_VERSION:
		raise HTTPException(
			status_code=400,
			detail=f"Unsupported backup version {payload.version}; this app reads version {BACKUP_VERSION}",
		)

	deleted = 0
	if mode is ImportMode.replace:
		# `query(...).delete()` is a BULK delete: it emits one DELETE statement and
		# runs no ORM cascades at all. The delete-orphan rules on Tracker.updates
		# and Tracker.rules do NOT fire here, so every child table has to be listed
		# by hand. Miss one and its rows survive pointing at ids that no longer
		# exist — and because updates carry a unique column, those orphans then
		# block the very rows the import is trying to restore.
		for model in (Update, UnmatchedMail, MatchRule):
			db.query(model).delete()

		# Children first — SQLite isn't enforcing the foreign keys, but deleting
		# in dependency order keeps the intent readable and stays correct if
		# PRAGMA foreign_keys is ever turned on.
		#
		# Only these four are counted: `deleted` is shown to the user as "how much
		# did I just wipe", and padding it with derived rows the poller rebuilds
		# on its own would make the number meaningless.
		for model in (Tracker, Subject, Platform, Category):
			deleted += db.query(model).delete()

	# Everything below works off these in-memory maps rather than re-querying,
	# because SessionLocal sets autoflush=False: a Category added moments ago is
	# NOT visible to a db.query() until flush, so a lookup would miss it and
	# create a duplicate.
	categories = {c.name: c for c in db.query(Category).all()}
	platforms = {p.name: p for p in db.query(Platform).all()}
	subjects = {s.name: s for s in db.query(Subject).all()}
	# Unique columns a single file can violate against ITSELF, so they need the
	# same in-memory tracking the tracker triple gets — a db.query() wouldn't see
	# rows added moments ago under autoflush=False. In replace mode both start
	# empty, since the bulk deletes above already hit the database.
	used_domains = {p.mail_domain for p in platforms.values() if p.mail_domain}
	# Trackers have no unique constraint, so "already present" has to be defined
	# here. The key is the whole (subject, platform, url) triple rather than the
	# url alone: two subjects can legitimately point at the same page, and
	# collapsing those loses a row.
	#
	# In replace mode the table was just emptied, so nothing can already be
	# present and every row in the file is inserted. This set is also NOT added
	# to as rows are inserted — otherwise two identical rows in one file would
	# collide with each other, and a restore would silently drop the second.
	if mode is ImportMode.replace:
		existing_trackers: set[tuple[str, str, str]] = set()
	else:
		existing_trackers = {
			(t.subject.name, t.platform.name, t.url)
			for t in db.query(Tracker)
			.options(joinedload(Tracker.subject), joinedload(Tracker.platform))
			.all()
		}

	added = {"categories": 0, "platforms": 0, "subjects": 0, "trackers": 0}
	skipped = 0

	for item in payload.categories:
		if item.name in categories:
			skipped += 1
			continue
		categories[item.name] = Category(
			name=item.name, date_created=item.date_created or utcnow()
		)
		db.add(categories[item.name])
		added["categories"] += 1

	for item in payload.platforms:
		if item.name in platforms:
			skipped += 1
			continue

		domain = item.mail_domain.lower() if item.mail_domain else None
		if domain and domain in used_domains:
			# Reached only when a DIFFERENT platform name claims a domain already
			# spoken for — same-named platforms are skipped above. Two platforms
			# on one domain makes every message from it ambiguous, so refuse
			# rather than silently drop the domain and leave matching broken.
			raise HTTPException(
				status_code=400,
				detail=f"Platform '{item.name}' reuses mail domain '{domain}'",
			)
		if domain:
			used_domains.add(domain)

		platforms[item.name] = Platform(
			name=item.name, mail_domain=domain, date_created=item.date_created or utcnow()
		)
		db.add(platforms[item.name])
		added["platforms"] += 1

	if mode is ImportMode.replace:
		# Replace mode can accept old version-1 backups from before Patreon Mail was
		# built in. Restore the app's built-ins inside the same transaction so a
		# successful import cannot leave them missing until the next restart.
		db.flush()
		ensure_predefined_platforms(db)
		db.flush()
		platforms = {p.name: p for p in db.query(Platform).all()}

	for item in payload.subjects:
		if item.name in subjects:
			skipped += 1
			continue
		category = None
		if item.category_name:
			category = categories.get(item.category_name)
			if category is None:
				# Nothing has been committed yet, so raising here leaves the
				# database exactly as it was — including the replace-mode deletes.
				raise HTTPException(
					status_code=400,
					detail=f"Subject '{item.name}' references unknown category '{item.category_name}'",
				)
		subjects[item.name] = Subject(
			name=item.name,
			category=category,
			date_created=item.date_created or utcnow(),
		)
		db.add(subjects[item.name])
		added["subjects"] += 1

	for item in payload.trackers:
		if (item.subject_name, item.platform_name, item.url) in existing_trackers:
			skipped += 1
			continue
		subject = subjects.get(item.subject_name)
		if subject is None:
			raise HTTPException(
				status_code=400,
				detail=f"Tracker '{item.name}' references unknown subject '{item.subject_name}'",
			)
		platform = platforms.get(item.platform_name)
		if platform is None:
			raise HTTPException(
				status_code=400,
				detail=f"Tracker '{item.name}' references unknown platform '{item.platform_name}'",
			)
		restored = Tracker(
			name=item.name,
			subject=subject,
			platform=platform,
			url=item.url,
			description=item.description,
			date_created=item.date_created or utcnow(),
			last_checked=item.last_checked,
		)
		# Rules are configuration, so they ride along with the tracker. Set through
		# the same helper the routes use, which normalises and de-duplicates.
		_set_rules(restored, item.rules)
		db.add(restored)
		added["trackers"] += 1

	db.commit()

	return ImportResult(
		mode=mode,
		categories_added=added["categories"],
		platforms_added=added["platforms"],
		subjects_added=added["subjects"],
		trackers_added=added["trackers"],
		skipped=skipped,
		deleted=deleted,
	)

@mail_router.post("/poll", response_model=PollResult)
def poll_mail(
	db: Session = Depends(get_db),
	config=Depends(get_mail_config),
	fetcher=Depends(get_mail_fetcher),
):
	schedule = _schedule(db)
	# 503 rather than 500: nothing is broken, the feature simply hasn't been set
	# up, and the message says exactly which variables are missing.
	if config is None:
		raise HTTPException(
			status_code=503,
			detail=(
				"Mailbox is not configured. Set ARTRACKER_MAIL_HOST, "
				"ARTRACKER_MAIL_USER and ARTRACKER_MAIL_PASSWORD."
			),
		)

	try:
		batch = fetcher(config, schedule.last_uid, schedule.uid_validity)
	except MailError as error:
		schedule.last_run_at = utcnow()
		schedule.last_result = f"Failed: {error}"[:500]
		db.commit()
		# 502: the app is fine, the upstream mailbox isn't.
		raise HTTPException(
			status_code=502, detail=f"Could not read the mailbox: {error}"
		) from error

	outcome = record_batch(db, schedule, batch)
	schedule.last_run_at = utcnow()
	schedule.last_result = (
		f"{len(batch.messages)} read, {outcome.recorded} recorded, "
		f"{outcome.duplicates} already seen, {outcome.unmatched} unmatched"
	)[:500]
	db.commit()
	return PollResult(
		fetched=len(batch.messages),
		recorded=outcome.recorded,
		duplicates=outcome.duplicates,
		unmatched=outcome.unmatched,
	)

# The visible half of "don't fail silently". Sender addresses and subject formats
# change without notice, and without somewhere to look, a broken rule is
# indistinguishable from an artist who simply hasn't posted.
@mail_router.get("/unmatched", response_model=list[UnmatchedMailOut])
def get_unmatched_mail(db: Session = Depends(get_db)):
	return db.query(UnmatchedMail).order_by(UnmatchedMail.received_at.desc()).all()

@mail_router.delete("/unmatched/{unmatched_id}", status_code=204)
def dismiss_unmatched_mail(unmatched_id: int, db: Session = Depends(get_db)):
	unmatched = db.query(UnmatchedMail).filter(UnmatchedMail.id == unmatched_id).first()
	if not unmatched:
		raise HTTPException(status_code=404, detail="Unmatched mail not found")

	db.delete(unmatched)
	db.commit()

# The mailbox the poller reads. Stored rather than env-only so it can be set from
# the Settings page; mail.resolve_mail_config falls back to ARTRACKER_MAIL_* when
# no row exists, so containers configured the old way keep working.
def _mail_account(db: Session) -> MailAccount | None:
	return db.query(MailAccount).first()


def _reset_mail_cursor(db: Session) -> None:
	"""Forget mailbox-specific UID state without changing the schedule itself."""
	schedule = db.query(PollSchedule).first()
	if schedule:
		schedule.last_uid = None
		schedule.uid_validity = None

@mail_router.get("/account", response_model=MailAccountOut)
def get_mail_account(db: Session = Depends(get_db)):
	account = _mail_account(db)
	if account:
		return MailAccountOut(
			host=account.host,
			port=account.port,
			username=account.username,
			mailbox=account.mailbox or "INBOX",
			has_password=bool(account.password),
			source="database",
		)

	# Nothing stored, so report whatever the environment provides. Returning the
	# env values rather than a blank form is what stops the Settings page from
	# claiming a working deployment is unconfigured.
	env = mail_config_from_env()
	if env:
		return MailAccountOut(
			host=env.host,
			port=env.port,
			username=env.user,
			mailbox=env.mailbox,
			has_password=True,
			source="environment",
		)

	return MailAccountOut(
		host="", port=993, username="", mailbox="INBOX", has_password=False, source="unset"
	)

@mail_router.put("/account", response_model=MailAccountOut)
def set_mail_account(payload: MailAccountIn, db: Session = Depends(get_db)):
	account = _mail_account(db)
	old_identity = (
		(account.host, account.port, account.username, account.mailbox or "INBOX")
		if account
		else None
	)

	if account is None:
		# First save has to carry a password; there is nothing to fall back on.
		if not payload.password:
			raise HTTPException(status_code=400, detail="A password is required")
		account = MailAccount(password=payload.password)
		db.add(account)

	account.host = payload.host
	account.port = payload.port
	account.username = payload.username
	account.mailbox = payload.mailbox
	# Omitted means "keep the stored one". The UI never receives the password
	# back, so it has nothing to send unless the user is actually changing it —
	# without this, editing the host would wipe the credential.
	if payload.password:
		account.password = payload.password
	account.updated_at = utcnow()

	new_identity = (account.host, account.port, account.username, account.mailbox or "INBOX")
	if old_identity != new_identity:
		# IMAP UIDs only have meaning inside one account and mailbox. Reusing the
		# old cursor after changing either can skip the beginning of the new inbox.
		_reset_mail_cursor(db)

	db.commit()

	return MailAccountOut(
		host=account.host,
		port=account.port,
		username=account.username,
		mailbox=account.mailbox,
		has_password=bool(account.password),
		source="database",
	)

@mail_router.delete("/account", status_code=204)
def clear_mail_account(db: Session = Depends(get_db)):
	account = _mail_account(db)
	if not account:
		raise HTTPException(status_code=404, detail="No mailbox is stored")

	# Deleting the row falls back to the environment rather than disabling the
	# feature outright, which is the point of keeping that path alive. The fallback
	# is a different mailbox identity, so its UID cursor must start fresh.
	db.delete(account)
	_reset_mail_cursor(db)
	db.commit()

# The background poller's schedule. Stored rather than passed as an env var so it
# can be changed from Settings without restarting the container.
def _schedule(db: Session) -> PollSchedule:
	"""The single schedule row, created on first read.

	Created lazily rather than seeded at startup so the table stays empty — and
	the poller stays off — until someone actually looks at the setting.
	"""
	schedule = db.query(PollSchedule).first()
	if schedule is None:
		schedule = PollSchedule()
		db.add(schedule)
		db.commit()
	return schedule


def _schedule_out(schedule: PollSchedule) -> PollScheduleOut:
	next_run = None
	if schedule.enabled:
		# From the last run, not from now, so reading the setting doesn't appear
		# to push the next run further away.
		next_run = (
			schedule.last_run_at + timedelta(minutes=schedule.interval_minutes)
			if schedule.last_run_at
			else utcnow()
		)

	return PollScheduleOut(
		enabled=schedule.enabled,
		interval_minutes=schedule.interval_minutes,
		last_run_at=schedule.last_run_at,
		last_result=schedule.last_result,
		next_run_at=next_run,
	)


@mail_router.get("/schedule", response_model=PollScheduleOut)
def get_poll_schedule(db: Session = Depends(get_db)):
	return _schedule_out(_schedule(db))

@mail_router.put("/schedule", response_model=PollScheduleOut)
def set_poll_schedule(payload: PollScheduleIn, db: Session = Depends(get_db)):
	schedule = _schedule(db)
	schedule.enabled = payload.enabled
	schedule.interval_minutes = payload.interval_minutes
	db.commit()

	return _schedule_out(schedule)
