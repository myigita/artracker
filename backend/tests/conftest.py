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
	def override_get_db():
		yield db_session

	app.dependency_overrides[get_db] = override_get_db
	try:
		yield TestClient(app)
	finally:
		app.dependency_overrides.clear()


@pytest.fixture
def subject(client):
	return client.post("/api/subjects/", json={"name": "Denji"}).json()


@pytest.fixture
def platform(client):
	return client.post("/api/platforms/", json={"name": "Pixiv"}).json()


@pytest.fixture
def category(client):
	return client.post("/api/categories/", json={"name": "Character"}).json()
