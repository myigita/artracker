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
