import os

from sqlalchemy import create_engine
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

Base.metadata.create_all(bind=engine)