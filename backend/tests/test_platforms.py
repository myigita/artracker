"""Platform endpoints. Same shape as subjects."""


def test_create_platform(client):
	response = client.post("/api/platforms/", json={"name": "Pixiv"})

	assert response.status_code == 201
	assert response.json()["name"] == "Pixiv"
	assert response.json()["id"] is not None


def test_duplicate_platform_is_rejected(client):
	client.post("/api/platforms/", json={"name": "Pixiv"})
	response = client.post("/api/platforms/", json={"name": "Pixiv"})

	assert response.status_code == 409


def test_platforms_listed_alphabetically(client):
	for name in ["Pixiv", "Bluesky", "Danbooru"]:
		client.post("/api/platforms/", json={"name": name})

	response = client.get("/api/platforms/")

	assert response.status_code == 200
	assert [p["name"] for p in response.json()] == ["Bluesky", "Danbooru", "Pixiv"]


def test_delete_unused_platform(client, platform):
	response = client.delete(f"/api/platforms/{platform['id']}")

	assert response.status_code == 204
	assert client.get("/api/platforms/").json() == []


def test_delete_missing_platform_404s(client):
	response = client.delete("/api/platforms/999999")

	assert response.status_code == 404


def test_cannot_delete_platform_still_in_use(client, subject, platform):
	# The guard that stands in for SQLite's disabled foreign keys.
	client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"url": "https://example.test/a",
		},
	)

	response = client.delete(f"/api/platforms/{platform['id']}")

	assert response.status_code == 409
	assert "tracker" in response.json()["detail"].lower()
	# and it's still there
	assert len(client.get("/api/platforms/").json()) == 1


# ---- notification-mail configuration ---------------------------------------

def test_platform_has_no_mail_domain_by_default(client, platform):
	assert platform["mail_domain"] is None


def test_create_platform_with_a_mail_domain(client):
	response = client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)

	assert response.status_code == 201
	assert response.json()["mail_domain"] == "creator.patreon.com"


def test_mail_domain_is_lowercased(client):
	body = client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "Creator.Patreon.COM"},
	).json()

	assert body["mail_domain"] == "creator.patreon.com"


def test_two_platforms_cannot_share_a_mail_domain(client):
	# One domain resolving to two platforms makes every message from it
	# ambiguous, so this is a 409 rather than a silently dropped field.
	client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)

	response = client.post(
		"/api/platforms/",
		json={"name": "Patreon Mail 2", "mail_domain": "creator.patreon.com"},
	)

	assert response.status_code == 409
	assert "creator.patreon.com" in response.json()["detail"]


def test_mail_domain_survives_a_backup_round_trip(client):
	client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)
	document = client.get("/api/backup/export").json()

	assert document["platforms"][0]["mail_domain"] == "creator.patreon.com"

	client.post("/api/backup/import?mode=replace", json=document)

	assert client.get("/api/platforms/").json()[0]["mail_domain"] == "creator.patreon.com"


def test_import_rejects_two_platforms_sharing_a_domain(client):
	document = {
		"version": 1,
		"platforms": [
			{"name": "One", "mail_domain": "creator.patreon.com"},
			{"name": "Two", "mail_domain": "creator.patreon.com"},
		],
	}

	response = client.post("/api/backup/import?mode=replace", json=document)

	assert response.status_code == 400


def test_import_allows_many_platforms_without_a_domain(client):
	# The NULL case must not trip the duplicate check — most platforms are
	# link-only and leave the field empty.
	document = {
		"version": 1,
		"platforms": [{"name": "Pixiv"}, {"name": "Bluesky"}, {"name": "Danbooru"}],
	}

	response = client.post("/api/backup/import?mode=replace", json=document)

	assert response.status_code == 200
	assert response.json()["platforms_added"] == 3
