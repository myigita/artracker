from fastapi import APIRouter, HTTPException, Depends

from .database import get_db
from .models import Subject, Tracker, Platform
from .schemas import (
	TrackerIn,
	TrackerOut,
	SubjectIn,
	SubjectOut,
	PlatformIn,
	PlatformOut,
)
from datetime import datetime
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/trackers")
subjects_router = APIRouter(prefix="/api/subjects")
platforms_router = APIRouter(prefix="/api/platforms")

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

@router.post("/", response_model=TrackerOut)
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

@router.post("/{tracker_id}/check", response_model=TrackerOut)
def check_tracker(tracker_id: int, db: Session = Depends(get_db)):
	tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
	if not tracker:
		raise HTTPException(status_code=404, detail="Tracker not found")

	tracker.last_checked = datetime.utcnow()
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

@subjects_router.get("/", response_model=list[SubjectOut])
def get_subjects(db: Session = Depends(get_db)):
	return db.query(Subject).order_by(Subject.name).all()

@subjects_router.post("/", response_model=SubjectOut, status_code=201)
def create_subject(subject_in: SubjectIn, db: Session = Depends(get_db)):
	existing = db.query(Subject).filter(Subject.name == subject_in.name).first()
	if existing:
		raise HTTPException(status_code=409, detail="Subject already exists")

	subject = Subject(name=subject_in.name)
	db.add(subject)
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
