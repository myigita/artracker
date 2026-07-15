"""Shared test fixtures.

pytest loads this file automatically — tests just name a fixture as a
parameter and pytest passes it in. No imports needed in the test files.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base


@pytest.fixture
def db_session():
	"""A fresh, empty, in-memory database — one per test.

	"sqlite://" (no filename) lives entirely in RAM and disappears afterwards,
	so tests never touch the real artracker.db and never depend on what's in it.

	StaticPool is load-bearing: in-memory SQLite gives each *connection* its own
	separate blank database. With normal pooling, create_all() would build the
	tables on one connection and the test would query a different, empty one —
	failing with "no such table". StaticPool forces one shared connection.

	expire_on_commit=False mirrors database.py, so tests exercise the same
	post-commit behaviour the app has in production.
	"""
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=engine)
	TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
	session = TestingSessionLocal()
	try:
		yield session
	finally:
		session.close()
		engine.dispose()


@pytest.fixture
def client(db_session):
	"""A TestClient whose app talks to db_session instead of the real DB.

	dependency_overrides swaps get_db for every route at once — routes.py is
	untouched and none of it knows it's under test. This only works because the
	routes take their session via Depends(get_db) rather than building one.
	"""
	def override_get_db():
		yield db_session

	app.dependency_overrides[get_db] = override_get_db
	try:
		yield TestClient(app)
	finally:
		# Undo the override so it can't leak into another test.
		app.dependency_overrides.clear()


@pytest.fixture
def subject(client):
	"""A subject that already exists. Returns the response JSON."""
	return client.post("/api/subjects/", json={"name": "Denji"}).json()


@pytest.fixture
def platform(client):
	"""A platform that already exists. Returns the response JSON."""
	return client.post("/api/platforms/", json={"name": "Pixiv"}).json()
