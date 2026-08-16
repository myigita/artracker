"""Backup export/import.

The atomicity test at the bottom is the important one: a file that fails
validation halfway through must leave the database untouched, including the
deletes that replace mode has already issued.
"""


def seed(client):
	"""Two categories' worth of a realistic database. Returns the export."""
	client.post("/api/categories/", json={"name": "Artist"})
	client.post("/api/platforms/", json={"name": "Pixiv"})
	client.post("/api/subjects/", json={"name": "Denji", "category_name": "Artist"})
	client.post(
		"/api/trackers/",
		json={
			"subject_name": "Denji",
			"platform_name": "Pixiv",
			"url": "https://example.test/denji",
		},
	)
	return client.get("/api/backup/export").json()


def test_export_contains_every_table(client):
	body = seed(client)

	assert body["version"] == 1
	assert [c["name"] for c in body["categories"]] == ["Artist"]
	assert [p["name"] for p in body["platforms"]] == ["Pixiv"]
	assert [s["name"] for s in body["subjects"]] == ["Denji"]
	assert [t["url"] for t in body["trackers"]] == ["https://example.test/denji"]


def test_export_references_by_name_not_id(client):
	body = seed(client)

	assert body["subjects"][0]["category_name"] == "Artist"
	assert body["trackers"][0]["subject_name"] == "Denji"
	assert body["trackers"][0]["platform_name"] == "Pixiv"
	# ids are deliberately absent — nothing outside the DB depends on them
	assert "id" not in body["trackers"][0]
	assert "id" not in body["subjects"][0]


def test_export_of_empty_database(client):
	body = client.get("/api/backup/export").json()

	assert body["categories"] == []
	assert body["trackers"] == []


def test_import_restores_into_an_empty_database(client):
	backup = seed(client)
	# wipe by hand, the way a fresh deployment would start
	for tracker in client.get("/api/trackers/").json():
		client.delete(f"/api/trackers/{tracker['id']}")
	for subject in client.get("/api/subjects/").json():
		client.delete(f"/api/subjects/{subject['id']}")
	for platform in client.get("/api/platforms/").json():
		client.delete(f"/api/platforms/{platform['id']}")
	for category in client.get("/api/categories/").json():
		client.delete(f"/api/categories/{category['id']}")

	response = client.post("/api/backup/import?mode=replace", json=backup)

	assert response.status_code == 200
	assert response.json()["trackers_added"] == 1
	restored = client.get("/api/trackers/").json()[0]
	assert restored["subject_name"] == "Denji"
	assert restored["subject_category"] == "Artist"
	assert restored["url"] == "https://example.test/denji"


def test_import_preserves_timestamps(client):
	backup = seed(client)
	client.post(f"/api/trackers/{client.get('/api/trackers/').json()[0]['id']}/check")
	backup = client.get("/api/backup/export").json()
	original = backup["trackers"][0]

	client.post("/api/backup/import?mode=replace", json=backup)

	restored = client.get("/api/trackers/").json()[0]
	assert restored["date_created"] == original["date_created"]
	assert restored["last_checked"] == original["last_checked"]


def test_merge_skips_what_already_exists(client):
	backup = seed(client)

	response = client.post("/api/backup/import?mode=merge", json=backup)

	assert response.status_code == 200
	body = response.json()
	assert body["trackers_added"] == 0
	assert body["skipped"] == 4
	assert body["deleted"] == 0
	# still one of each, not two
	assert len(client.get("/api/trackers/").json()) == 1
	assert len(client.get("/api/subjects/").json()) == 1


def test_merge_adds_only_what_is_missing(client):
	backup = seed(client)
	backup["platforms"].append({"name": "Bluesky"})
	backup["trackers"].append({
		"name": "Denji on Bluesky",
		"subject_name": "Denji",
		"platform_name": "Bluesky",
		"url": "https://example.test/new",
	})

	body = client.post("/api/backup/import?mode=merge", json=backup).json()

	assert body["platforms_added"] == 1
	assert body["trackers_added"] == 1
	assert len(client.get("/api/trackers/").json()) == 2


def test_merge_keeps_local_edits(client):
	"""Merge is additive: a tracker already here is left exactly as it is."""
	backup = seed(client)
	tracker_id = client.get("/api/trackers/").json()[0]["id"]
	client.patch(f"/api/trackers/{tracker_id}", json={"name": "Renamed locally"})

	client.post("/api/backup/import?mode=merge", json=backup)

	assert client.get("/api/trackers/").json()[0]["name"] == "Renamed locally"


def test_replace_removes_data_absent_from_the_file(client):
	backup = seed(client)
	client.post("/api/platforms/", json={"name": "Danbooru"})
	client.post("/api/subjects/", json={"name": "Power"})

	body = client.post("/api/backup/import?mode=replace", json=backup).json()

	assert body["deleted"] > 0
	assert [s["name"] for s in client.get("/api/subjects/").json()] == ["Denji"]
	assert [p["name"] for p in client.get("/api/platforms/").json()] == ["Pixiv"]


def test_replace_is_idempotent(client):
	backup = seed(client)

	client.post("/api/backup/import?mode=replace", json=backup)
	client.post("/api/backup/import?mode=replace", json=backup)

	assert len(client.get("/api/trackers/").json()) == 1
	assert len(client.get("/api/subjects/").json()) == 1


def test_merge_is_the_default_mode(client):
	backup = seed(client)

	body = client.post("/api/backup/import", json=backup).json()

	assert body["mode"] == "merge"
	assert body["deleted"] == 0


def test_unknown_mode_is_rejected(client):
	backup = seed(client)

	assert client.post("/api/backup/import?mode=obliterate", json=backup).status_code == 422


def test_future_version_is_rejected(client):
	backup = seed(client)
	backup["version"] = 99

	response = client.post("/api/backup/import?mode=replace", json=backup)

	assert response.status_code == 400
	assert "version" in response.json()["detail"].lower()
	# and the existing data survived
	assert len(client.get("/api/trackers/").json()) == 1


def test_tracker_referencing_unknown_subject_400s(client):
	backup = seed(client)
	backup["trackers"].append({
		"name": "Orphan",
		"subject_name": "Nobody",
		"platform_name": "Pixiv",
		"url": "https://example.test/orphan",
	})

	response = client.post("/api/backup/import?mode=merge", json=backup)

	assert response.status_code == 400
	assert "Nobody" in response.json()["detail"]


def test_a_rejected_import_changes_nothing(client):
	"""REGRESSION GUARD: replace mode deletes before it inserts. If a later row
	fails validation, those deletes must roll back too — otherwise a typo in a
	backup file empties the database."""
	seed(client)
	before_trackers = client.get("/api/trackers/").json()
	before_subjects = client.get("/api/subjects/").json()

	bad = client.get("/api/backup/export").json()
	bad["trackers"].append({
		"name": "Orphan",
		"subject_name": "Nobody",
		"platform_name": "Pixiv",
		"url": "https://example.test/orphan",
	})

	assert client.post("/api/backup/import?mode=replace", json=bad).status_code == 400

	assert client.get("/api/trackers/").json() == before_trackers
	assert client.get("/api/subjects/").json() == before_subjects


def test_import_rejects_malformed_rows(client):
	response = client.post(
		"/api/backup/import?mode=merge",
		json={"version": 1, "subjects": [{"name": ""}]},
	)

	assert response.status_code == 422


def test_import_of_an_empty_document_is_a_noop(client):
	seed(client)

	body = client.post("/api/backup/import?mode=merge", json={"version": 1}).json()

	assert body["subjects_added"] == 0
	assert len(client.get("/api/trackers/").json()) == 1
