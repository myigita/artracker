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
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/trackers")
subjects_router = APIRouter(prefix="/api/subjects")
platforms_router = APIRouter(prefix="/api/platforms")
categories_router = APIRouter(prefix="/api/categories")

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
