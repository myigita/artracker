from datetime import datetime, timezone

from app.models import Tracker


def make_tracker(client, subject, platform, url="https://example.test/a", **extra):
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

	assert body["name"] == "Denji (Pixiv)"


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
	make_tracker(client, subject, platform)

	response = client.get("/api/trackers/")

	assert response.status_code == 200
	assert response.json()[0]["subject_name"] == "Denji"
	assert response.json()[0]["platform_name"] == "Pixiv"


def test_trackers_listed_newest_first(client, subject, platform, db_session):
	older = make_tracker(client, subject, platform, url="https://example.test/old").json()
	newer = make_tracker(client, subject, platform, url="https://example.test/new").json()

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
	created = make_tracker(client, subject, platform).json()
	checked = client.post(f"/api/trackers/{created['id']}/check").json()

	assert checked["date_created"].endswith("+00:00")
	assert checked["last_checked"].endswith("+00:00")


def test_last_checked_is_actually_now_in_utc(client, subject, platform):
	created = make_tracker(client, subject, platform).json()
	checked = client.post(f"/api/trackers/{created['id']}/check").json()

	parsed = datetime.fromisoformat(checked["last_checked"])
	drift = abs((datetime.now(timezone.utc) - parsed).total_seconds())

	assert drift < 10, f"last_checked is {drift}s from now — wrong timezone?"


def test_update_tracker_changes_only_sent_fields(client, subject, platform):
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
	created = make_tracker(client, subject, platform).json()
	client.patch(f"/api/trackers/{created['id']}", json={"name": "Persisted"})

	assert client.get(f"/api/trackers/{created['id']}").json()["name"] == "Persisted"


def test_update_rejects_empty_name(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	assert client.patch(f"/api/trackers/{created['id']}", json={"name": ""}).status_code == 422


def test_update_rejects_empty_url(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	assert client.patch(f"/api/trackers/{created['id']}", json={"url": ""}).status_code == 400


def test_update_missing_tracker_404s(client):
	assert client.patch("/api/trackers/999999", json={"name": "x"}).status_code == 404


def test_empty_patch_is_a_noop(client, subject, platform):
	created = make_tracker(client, subject, platform, name="Untouched").json()

	body = client.patch(f"/api/trackers/{created['id']}", json={}).json()

	assert body["name"] == "Untouched"


def test_create_rejects_oversized_field(client, subject, platform):
	response = make_tracker(client, subject, platform, name="A" * 100_000)

	assert response.status_code == 422


def test_create_rejects_empty_url(client, subject, platform):
	assert make_tracker(client, subject, platform, url="").status_code == 400


def test_create_rejects_whitespace_only_name(client, subject, platform):
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
	created = make_tracker(client, subject, platform).json()

	assert client.patch(
		f"/api/trackers/{created['id']}", json={"name": None}
	).status_code == 400


def test_undo_restores_previous_last_checked(client, subject, platform):
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")
	stamped = client.get(f"/api/trackers/{created['id']}").json()["last_checked"]
	assert stamped is not None

	client.post(f"/api/trackers/{created['id']}/check")
	response = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": stamped}
	)

	assert response.status_code == 200
	assert response.json()["last_checked"] == stamped


def test_undo_can_restore_never_checked(client, subject, platform):
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")

	response = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": None}
	)

	assert response.status_code == 200
	assert response.json()["last_checked"] is None


def test_inbound_last_checked_is_converted_to_utc(client, subject, platform):
	created = make_tracker(client, subject, platform).json()

	body = client.patch(
		f"/api/trackers/{created['id']}",
		json={"last_checked": "2026-08-15T12:00:00+03:00"},
	).json()

	assert body["last_checked"] == "2026-08-15T09:00:00+00:00"


def test_undo_round_trips_through_the_wire_format(client, subject, platform):
	created = make_tracker(client, subject, platform).json()
	client.post(f"/api/trackers/{created['id']}/check")
	original = client.get(f"/api/trackers/{created['id']}").json()["last_checked"]

	client.patch(f"/api/trackers/{created['id']}", json={"last_checked": None})
	restored = client.patch(
		f"/api/trackers/{created['id']}", json={"last_checked": original}
	).json()["last_checked"]

	assert restored == original


def test_tracker_exposes_subject_category(client, subject, platform, category):
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})
	make_tracker(client, subject, platform)

	response = client.get("/api/trackers/")

	assert response.status_code == 200
	assert response.json()[0]["subject_category"] == "Character"


def test_tracker_subject_category_is_null_when_uncategorized(client, subject, platform):
	body = make_tracker(client, subject, platform).json()

	assert body["subject_category"] is None


def test_tracker_subject_category_follows_the_subject(client, subject, platform, category):
	make_tracker(client, subject, platform)
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})

	assert client.get("/api/trackers/").json()[0]["subject_category"] == "Character"

	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": None})

	assert client.get("/api/trackers/").json()[0]["subject_category"] is None


def mail_platform(client):
	return client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	).json()


def test_a_platform_domain_is_not_used_as_an_artist_rule(client, subject):
	mail_platform(client)

	response = client.post(
		"/api/trackers/",
		json={"subject_name": subject["name"], "platform_name": "Patreon - Mail"},
	)

	assert response.status_code == 400
	assert "match rule" in response.json()["detail"]


def test_a_mail_tracker_with_a_specific_rule_needs_no_url(client, subject):
	mail_platform(client)

	response = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Patreon - Mail",
			"rules": [{"field": "sender", "operator": "contains", "value": "denji"}],
		},
	)

	assert response.status_code == 201
	assert response.json()["url"] == ""


def test_a_tracker_with_neither_url_nor_rules_is_rejected(client, subject, platform):
	response = client.post(
		"/api/trackers/",
		json={"subject_name": subject["name"], "platform_name": platform["name"]},
	)

	assert response.status_code == 400
	assert "match rule" in response.json()["detail"]


def test_rules_alone_are_enough_without_a_url(client, subject, platform):
	response = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"rules": [{"field": "sender", "operator": "contains", "value": "pixiv.net"}],
		},
	)

	assert response.status_code == 201
	assert response.json()["url"] == ""
	assert len(response.json()["rules"]) == 1


def test_a_blank_url_is_treated_as_absent(client, subject, platform):
	response = client.post(
		"/api/trackers/",
		json={"subject_name": subject["name"], "platform_name": platform["name"], "url": "   "},
	)

	assert response.status_code == 400


def test_the_url_can_be_cleared_when_rules_remain(client, subject):
	mail_platform(client)
	created = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Patreon - Mail",
			"url": "https://patreon.com/peargor",
			"rules": [{"field": "sender", "operator": "contains", "value": "peargor"}],
		},
	).json()

	response = client.patch(f"/api/trackers/{created['id']}", json={"url": ""})

	assert response.status_code == 200
	assert response.json()["url"] == ""


def test_the_url_cannot_be_cleared_when_there_are_no_rules(client, subject, platform):
	created = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"url": "https://example.test/a",
		},
	).json()

	response = client.patch(f"/api/trackers/{created['id']}", json={"url": ""})

	assert response.status_code == 400
	assert client.get(f"/api/trackers/{created['id']}").json()["url"] == "https://example.test/a"


def test_the_rules_cannot_be_cleared_when_there_is_no_url(client, subject, platform):
	created = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"rules": [{"field": "sender", "operator": "contains", "value": "pixiv.net"}],
		},
	).json()

	assert client.patch(f"/api/trackers/{created['id']}", json={"rules": []}).status_code == 400


def test_the_default_name_uses_parentheses(client, subject):
	mail_platform(client)

	body = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Patreon - Mail",
			"rules": [{"field": "sender", "operator": "contains", "value": "denji"}],
		},
	).json()

	assert body["name"] == "Denji (Patreon - Mail)"
