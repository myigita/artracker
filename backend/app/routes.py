from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Tracker
from .schemas import TrackerOut

router = APIRouter(prefix="/api/trackers")

@router.get("/", response_model=list[TrackerOut])
async def get_trackers():
	db =  SessionLocal()
	try:
		trackers = db.query(Tracker).order_by(Tracker.created_at.desc()).all()
		return trackers
	except Exception as e:
		print(e)
	finally:
		db.close()

@router.get("/{tracker_id}", response_model=TrackerOut)
async def get_tracker(tracker_id: int):
	db = SessionLocal()
	try:
		tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
		if tracker:
			return tracker
		return None
	except Exception as e:
		print(e)
	finally:
		db.close()