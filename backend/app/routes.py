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
	trackers = (
		db.query(Tracker)
		.options(selectinload(Tracker.updates), selectinload(Tracker.rules))
		# populate_existing: the session may hold a stale `updates` collection.
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

	rules_in = tracker_in.rules or []

	name = tracker_in.name if tracker_in.name else f"{tracker_in.subject_name} ({tracker_in.platform_name})"

	tracker = Tracker(
		name=name,
		subject=subject,
		platform=platform,
		# NOT NULL column; SQLite can't relax it without rebuilding the table.
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

	changes = tracker_update.model_dump(exclude_unset=True)

	# Explicit null passes Pydantic. name/url are NOT NULL; description and last_checked may be cleared.
	if "name" in changes and not changes["name"]:
		raise HTTPException(status_code=400, detail="Name cannot be empty")
	if "url" in changes and not changes["url"]:
		changes["url"] = ""

	# model_dump turned rules into dicts, so they're applied separately.
	rules_sent = "rules" in changes
	changes.pop("rules", None)

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
	# Reload children so the delete-orphan cascade sees every row.
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

def _lookup_category(name: str, db: Session) -> Category:
	category = db.query(Category).filter(Category.name == name).first()
	if not category:
		raise HTTPException(status_code=400, detail="Invalid category")
	return category

# Mutate in place: reassigning the list makes SQLAlchemy rewrite every row.
def _set_rules(tracker: Tracker, rules: list[MatchRuleIn]) -> None:
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


def _require_url_or_rules(url: str, rules: list, name: str) -> None:
	if not url and not rules:
		raise HTTPException(
			status_code=400,
			detail=f"'{name}' needs a URL or at least one match rule",
		)

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

	# Explicit null clears the category; an omitted key leaves it alone.
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

	# Seeding would recreate it on the next boot.
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

	# SQLite doesn't enforce the FK, so this guard is the only protection.
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
		# Bulk delete skips ORM cascades, so child tables are cleared by hand.
		for model in (Update, UnmatchedMail, MatchRule):
			db.query(model).delete()

		for model in (Tracker, Subject, Platform, Category):
			deleted += db.query(model).delete()

	# In-memory maps: autoflush=False hides rows added earlier in this import.
	categories = {c.name: c for c in db.query(Category).all()}
	platforms = {p.name: p for p in db.query(Platform).all()}
	subjects = {s.name: s for s in db.query(Subject).all()}
	used_domains = {p.mail_domain for p in platforms.values() if p.mail_domain}
	# Keyed on the full triple, not url: two subjects can share a page.
	# Not added to while inserting, or duplicate rows in one file would collide.
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
		# Old backups predate the built-in platforms; restore them in the same transaction.
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

def _mail_account(db: Session) -> MailAccount | None:
	return db.query(MailAccount).first()


def _reset_mail_cursor(db: Session) -> None:
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
		if not payload.password:
			raise HTTPException(status_code=400, detail="A password is required")
		account = MailAccount(password=payload.password)
		db.add(account)

	account.host = payload.host
	account.port = payload.port
	account.username = payload.username
	account.mailbox = payload.mailbox
	# Omitted keeps the stored password; the UI never receives it.
	if payload.password:
		account.password = payload.password
	account.updated_at = utcnow()

	new_identity = (account.host, account.port, account.username, account.mailbox or "INBOX")
	if old_identity != new_identity:
		# UIDs only mean something within one account and mailbox.
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

	db.delete(account)
	_reset_mail_cursor(db)
	db.commit()

def _schedule(db: Session) -> PollSchedule:
	schedule = db.query(PollSchedule).first()
	if schedule is None:
		schedule = PollSchedule()
		db.add(schedule)
		db.commit()
	return schedule


def _schedule_out(schedule: PollSchedule) -> PollScheduleOut:
	next_run = None
	if schedule.enabled:
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
