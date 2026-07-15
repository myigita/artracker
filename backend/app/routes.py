from fastapi import APIRouter, HTTPException

from .database import SessionLocal
from .models import Subject, Tracker, Platform
from .schemas import TrackerIn, TrackerOut
from datetime import datetime

router = APIRouter(prefix="/api/trackers")

@router.get("/", response_model=list[TrackerOut])
def get_trackers():
	db =  SessionLocal()
	try:
		trackers = db.query(Tracker).order_by(Tracker.date_created.desc()).all()
		return trackers
	finally:
		db.close()

@router.get("/{tracker_id}", response_model=TrackerOut)
def get_tracker(tracker_id: int):
	db = SessionLocal()
	try:
		tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
		if tracker:
			return tracker
		raise HTTPException(status_code=404, detail="Tracker not found")
	finally:
		db.close()

@router.post("/", response_model=TrackerOut)
def create_tracker(tracker: TrackerIn):
	db = SessionLocal()
	try:

		subject = db.query(Subject).filter(Subject.name == tracker.subject_name).first()
		if not subject:
			raise HTTPException(status_code=400, detail="Invalid subject")

		platform = db.query(Platform).filter(Platform.name == tracker.platform_name).first()
		if not platform:
			raise HTTPException(status_code=400, detail="Invalid platform")

		name = tracker.name if tracker.name else f"{tracker.subject_name} - {tracker.platform_name}"

		tracker = Tracker(
			name=name,
			subject=subject,
			platform=platform,
			url=tracker.url,
			description=tracker.description
		)
		db.add(tracker)
		db.commit()
		return tracker
	finally:
		db.close()

@router.post("/{tracker_id}/check", response_model=TrackerOut)
def check_tracker(tracker_id: int):
	db = SessionLocal()
	try:
		tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
		if not tracker:
			raise HTTPException(status_code=404, detail="Tracker not found")

		tracker.last_checked = datetime.utcnow()
		db.commit()
		return tracker
	finally:
		db.close()