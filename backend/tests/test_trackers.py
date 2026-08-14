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


def test_update_tracker_changes_only_sent_fields(client, subject, platform):
	"""PATCH must leave omitted fields alone — not null them out.

	This is what `exclude_unset=True` buys: a form that only submits `url`
	must not wipe the tracker's name and description.
	"""
	created = make_tracker(client, subject, platform, name="Original", description="Original desc").json()

	response = client.patch(
		f"/api/trackers/{created['id']}",
		json={"url": "https://example.test/updated"},
	)

	assert response.status_code == 200
	body = response.json()
	assert body["url"] == "https://example.test/updated"
	assert body["name"] == "Original"
	assert body["description"] == "Original desc"


def test_update_can_set_description_to_null(client, subject, platform):
	"""Explicit null must differ from omission — clearing a field has to work."""
	created = make_tracker(client, subject, platform, description="Original desc").json()

	body = client.patch(
		f"/api/trackers/{created['id']}", json={"description": None}
	).json()

	assert body["description"] is None


def test_update_multiple_fields(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	body = client.patch(
		f"/api/trackers/{created['id']}",
		json={"name": "New name", "url": "https://example.test/new", "description": "New desc"},
	).json()

	assert body["name"] == "New name"
	assert body["url"] == "https://example.test/new"
	assert body["description"] == "New desc"


def test_update_persists(client, subject, platform):
	"""The change must survive the request, not just echo back."""
	created = make_tracker(client, subject, platform).json()
	client.patch(f"/api/trackers/{created['id']}", json={"name": "Persisted"})

	assert client.get(f"/api/trackers/{created['id']}").json()["name"] == "Persisted"


def test_update_rejects_empty_name(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	# 422, not 400: Pydantic's min_length rejects "" during request parsing,
	# before the route's own check runs. The route's 400 now only covers an
	# explicit JSON null — see test_update_rejects_explicit_null_name.
	assert client.patch(f"/api/trackers/{created['id']}", json={"name": ""}).status_code == 422


def test_update_rejects_empty_url(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	assert client.patch(f"/api/trackers/{created['id']}", json={"url": ""}).status_code == 422


def test_update_missing_tracker_404s(client):
	assert client.patch("/api/trackers/999999", json={"name": "x"}).status_code == 404


def test_empty_patch_is_a_noop(client, subject, platform):
	created = make_tracker(client, subject, platform, name="Untouched").json()

	body = client.patch(f"/api/trackers/{created['id']}", json={}).json()

	assert body["name"] == "Untouched"


def test_create_rejects_oversized_field(client, subject, platform):
	"""SQLite ignores VARCHAR lengths, so Pydantic is the only real bound.

	Before max_length was added, a 100KB name was accepted with a 201 —
	an unbounded write for anyone who can reach the API.
	"""
	response = make_tracker(client, subject, platform, name="A" * 100_000)

	assert response.status_code == 422


def test_create_rejects_empty_url(client, subject, platform):
	"""POST used to accept url="" while PATCH rejected it — inconsistent."""
	assert make_tracker(client, subject, platform, url="").status_code == 422


def test_create_rejects_whitespace_only_name(client, subject, platform):
	"""A whitespace name rendered as a blank card title in the UI."""
	assert make_tracker(client, subject, platform, name="   ").status_code == 422


def test_names_are_stripped(client, subject, platform):
	body = make_tracker(client, subject, platform, name="  Padded  ").json()

	assert body["name"] == "Padded"


def test_update_rejects_whitespace_only_name(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	assert client.patch(
		f"/api/trackers/{created['id']}", json={"name": "   "}
	).status_code == 422


def test_update_rejects_explicit_null_name(client, subject, platform):
	"""Pydantic allows null (the field is Optional); the route must catch it,
	or it writes NULL into a NOT NULL column and 500s."""
	created = make_tracker(client, subject, platform).json()

	assert client.patch(
		f"/api/trackers/{created['id']}", json={"name": None}
	).status_code == 400


def test_undo_restores_previous_last_checked(client, subject, platform):
	"""The undo button's whole job: put back the stamp that was there before."""
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")
	stamped = client.get(f"/api/trackers/{created['id']}").json()["last_checked"]
	assert stamped is not None

	# check again, then undo back to the first stamp
	client.post(f"/api/trackers/{created['id']}/check")
	response = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": stamped}
	)

	assert response.status_code == 200
	assert response.json()["last_checked"] == stamped


def test_undo_can_restore_never_checked(client, subject, platform):
	"""A tracker checked for the first time has no previous stamp, so undo sends
	null. That has to be allowed — unlike a null name, which 400s."""
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")

	response = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": None}
	)

	assert response.status_code == 200
	assert response.json()["last_checked"] is None


def test_inbound_last_checked_is_converted_to_utc(client, subject, platform):
	"""An aware datetime must be CONVERTED, not just stripped of its tzinfo.

	SQLite discards tzinfo on its own, but without converting — so a naive write
	of "12:00+03:00" would store 12:00 UTC and read back three hours late. The
	stored value has to be the same instant, 09:00Z.
	"""
	created = make_tracker(client, subject, platform).json()

	body = client.patch(
		f"/api/trackers/{created['id']}",
		json={"last_checked": "2026-08-15T12:00:00+03:00"},
	).json()

	assert body["last_checked"] == "2026-08-15T09:00:00+00:00"


def test_undo_round_trips_through_the_wire_format(client, subject, platform):
	"""The value the UI sends back is exactly the string the API gave it, so the
	serialize -> parse -> store -> serialize loop has to be lossless."""
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")
	original = client.get(f"/api/trackers/{created['id']}").json()["last_checked"]

	client.patch(f"/api/trackers/{created['id']}", json={"last_checked": None})
	restored = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": original}
	).json()["last_checked"]

	assert restored == original


def test_tracker_exposes_subject_category(client, subject, platform, category):
	"""subject_category is a TWO-hop lazy load (tracker -> subject -> category),
	so it's exposed to the same DetachedInstanceError that
	test_list_exposes_subject_and_platform_names pins down — one hop further out.
	Asserted on the list endpoint for that reason, not just on the POST response.
	"""
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})
	make_tracker(client, subject, platform)

	response = client.get("/api/trackers/")

	assert response.status_code == 200
	assert response.json()[0]["subject_category"] == "Character"


def test_tracker_subject_category_is_null_when_uncategorized(client, subject, platform):
	body = make_tracker(client, subject, platform).json()

	assert body["subject_category"] is None


def test_tracker_subject_category_follows_the_subject(client, subject, platform, category):
	"""It's derived, not copied — recategorizing the subject moves every tracker
	hanging off it, with no write to the trackers table."""
	make_tracker(client, subject, platform)
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})

	assert client.get("/api/trackers/").json()[0]["subject_category"] == "Character"

	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": None})

	assert client.get("/api/trackers/").json()[0]["subject_category"] is None
