from fastapi import APIRouter, HTTPException, Depends

from .database import get_db
from .models import Category, Subject, Tracker, Platform, utcnow
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
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/trackers")
subjects_router = APIRouter(prefix="/api/subjects")
platforms_router = APIRouter(prefix="/api/platforms")
categories_router = APIRouter(prefix="/api/categories")
backup_router = APIRouter(prefix="/api/backup")

@router.get("/", response_model=list[TrackerOut])
def get_trackers(db: Session = Depends(get_db)):
	trackers = db.query(Tracker).order_by(Tracker.date_created.desc()).all()
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

	name = tracker_in.name if tracker_in.name else f"{tracker_in.subject_name} - {tracker_in.platform_name}"

	tracker = Tracker(
		name=name,
		subject=subject,
		platform=platform,
		url=tracker_in.url,
		description=tracker_in.description
	)
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
	if "url" in changes and not changes["url"]:
		raise HTTPException(status_code=400, detail="URL cannot be empty")

	for field, value in changes.items():
		setattr(tracker, field, value)

	db.commit()
	return tracker

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
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
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

	platform = Platform(name=platform_in.name)
	db.add(platform)
	db.commit()
	return platform

@platforms_router.delete("/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
	platform = db.query(Platform).filter(Platform.id == platform_id).first()
	if not platform:
		raise HTTPException(status_code=404, detail="Platform not found")

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
		# Children first — SQLite isn't enforcing the foreign keys, but deleting
		# in dependency order keeps the intent readable and stays correct if
		# PRAGMA foreign_keys is ever turned on.
		for model in (Tracker, Subject, Platform, Category):
			deleted += db.query(model).delete()

	# Everything below works off these in-memory maps rather than re-querying,
	# because SessionLocal sets autoflush=False: a Category added moments ago is
	# NOT visible to a db.query() until flush, so a lookup would miss it and
	# create a duplicate.
	categories = {c.name: c for c in db.query(Category).all()}
	platforms = {p.name: p for p in db.query(Platform).all()}
	subjects = {s.name: s for s in db.query(Subject).all()}
	tracker_urls = {t.url for t in db.query(Tracker).all()}

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
		platforms[item.name] = Platform(
			name=item.name, date_created=item.date_created or utcnow()
		)
		db.add(platforms[item.name])
		added["platforms"] += 1

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
			name=item.name, category=category, date_created=item.date_created or utcnow()
		)
		db.add(subjects[item.name])
		added["subjects"] += 1

	for item in payload.trackers:
		# URL is the identity for merge purposes: it's what actually names the
		# destination, and tracker names are not unique.
		if item.url in tracker_urls:
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
		db.add(Tracker(
			name=item.name,
			subject=subject,
			platform=platform,
			url=item.url,
			description=item.description,
			date_created=item.date_created or utcnow(),
			last_checked=item.last_checked,
		))
		tracker_urls.add(item.url)
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
