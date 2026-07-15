"""Tracker endpoints.

Two of these are regression tests for bugs that actually happened — see
test_list_exposes_subject_and_platform_names and the timestamp tests at the
bottom. Don't delete them without understanding what they're pinning down.
"""
from datetime import datetime, timezone

from app.models import Tracker


def make_tracker(client, subject, platform, url="https://example.test/a", **extra):
	"""Create a tracker via the API and return its JSON."""
	payload = {
		"subject_name": subject["name"],
		"platform_name": platform["name"],
		"url": url,
	}
	payload.update(extra)
	return client.post("/api/trackers/", json=payload)


def test_create_tracker(client, subject, platform):
	response = make_tracker(client, subject, platform)

	assert response.status_code == 201
	body = response.json()
	assert body["url"] == "https://example.test/a"
	assert body["subject_name"] == "Denji"
	assert body["platform_name"] == "Pixiv"
	assert body["last_checked"] is None


def test_name_defaults_to_subject_and_platform(client, subject, platform):
	body = make_tracker(client, subject, platform).json()

	assert body["name"] == "Denji - Pixiv"


def test_explicit_name_is_kept(client, subject, platform):
	body = make_tracker(client, subject, platform, name="Denji fanart tag").json()

	assert body["name"] == "Denji fanart tag"


def test_description_is_optional(client, subject, platform):
	assert make_tracker(client, subject, platform).json()["description"] is None

	body = make_tracker(
		client, subject, platform, url="https://example.test/b", description="weekly"
	).json()
	assert body["description"] == "weekly"


def test_unknown_subject_is_rejected(client, platform):
	response = client.post(
		"/api/trackers/",
		json={
			"subject_name": "Nobody",
			"platform_name": platform["name"],
			"url": "https://example.test/a",
		},
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Invalid subject"


def test_unknown_platform_is_rejected(client, subject):
	response = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Nowhere",
			"url": "https://example.test/a",
		},
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Invalid platform"


def test_list_exposes_subject_and_platform_names(client, subject, platform):
	"""REGRESSION: this endpoint used to 500 in production.

	subject_name/platform_name are @propertys that lazy-load relationships, and
	the routes used to close their session before FastAPI serialized the
	response — so serialization raised DetachedInstanceError. Depends(get_db)
	keeps the session open through serialization.

	Verified by mutation: reverting get_trackers to a hand-rolled
	SessionLocal()/try/finally makes this test fail. Note it fails by returning
	[] rather than by 500ing, because a hand-rolled SessionLocal bypasses
	dependency_overrides and reads the *real* artracker.db instead of the test
	database. Either way, this test is what catches it.
	"""
	make_tracker(client, subject, platform)

	response = client.get("/api/trackers/")

	assert response.status_code == 200
	assert response.json()[0]["subject_name"] == "Denji"
	assert response.json()[0]["platform_name"] == "Pixiv"


def test_trackers_listed_newest_first(client, subject, platform, db_session):
	older = make_tracker(client, subject, platform, url="https://example.test/old").json()
	newer = make_tracker(client, subject, platform, url="https://example.test/new").json()

	# Both were created in the same instant, so force them apart rather than
	# depend on microsecond ordering (which would make this flaky).
	db_session.query(Tracker).filter(Tracker.id == older["id"]).update(
		{"date_created": datetime(2020, 1, 1)}
	)
	db_session.commit()

	response = client.get("/api/trackers/")

	assert [t["id"] for t in response.json()] == [newer["id"], older["id"]]


def test_get_one_tracker(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	response = client.get(f"/api/trackers/{created['id']}")

	assert response.status_code == 200
	assert response.json()["id"] == created["id"]


def test_get_missing_tracker_404s(client):
	assert client.get("/api/trackers/999999").status_code == 404


def test_check_stamps_last_checked(client, subject, platform):
	created = make_tracker(client, subject, platform).json()
	assert created["last_checked"] is None

	response = client.post(f"/api/trackers/{created['id']}/check")

	assert response.status_code == 200
	assert response.json()["last_checked"] is not None
	# returned so the UI can refresh the row in place
	assert response.json()["id"] == created["id"]


def test_check_missing_tracker_404s(client):
	assert client.post("/api/trackers/999999/check").status_code == 404


def test_delete_tracker(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	response = client.delete(f"/api/trackers/{created['id']}")

	assert response.status_code == 200
	assert client.get("/api/trackers/").json() == []


def test_delete_missing_tracker_404s(client):
	assert client.delete("/api/trackers/999999").status_code == 404


def test_timestamps_are_marked_utc(client, subject, platform):
	"""REGRESSION: timestamps used to serialize without a timezone marker.

	We store naive UTC (SQLite discards tzinfo), so a bare "2026-07-15T17:37:13"
	is read by JS `new Date()` as *local* time — silently skewing every stamp by
	the client's offset (3h here). schemas.UtcDatetime re-attaches the marker.
	If this fails, the frontend's "last checked" ageing is lying.
	"""
	created = make_tracker(client, subject, platform).json()
	checked = client.post(f"/api/trackers/{created['id']}/check").json()

	assert checked["date_created"].endswith("+00:00")
	assert checked["last_checked"].endswith("+00:00")


def test_last_checked_is_actually_now_in_utc(client, subject, platform):
	"""The marker being present isn't enough — the value must really be UTC."""
	created = make_tracker(client, subject, platform).json()
	checked = client.post(f"/api/trackers/{created['id']}/check").json()

	parsed = datetime.fromisoformat(checked["last_checked"])
	drift = abs((datetime.now(timezone.utc) - parsed).total_seconds())

	assert drift < 10, f"last_checked is {drift}s from now — wrong timezone?"
