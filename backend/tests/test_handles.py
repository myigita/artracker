"""Subject handles — what an artist is called on a platform.

These are the join between an incoming email's sender and a tracker, so the
uniqueness and normalisation rules here are what make mail matching deterministic
rather than a guess.
"""


def test_subject_has_no_handles_by_default(client, subject):
	assert subject["handles"] == []


def test_create_subject_with_handles(client):
	response = client.post(
		"/api/subjects/",
		json={"name": "Pear哥", "handles": ["peargor", "pear_art"]},
	)

	assert response.status_code == 201
	assert response.json()["handles"] == ["pear_art", "peargor"]


def test_handles_are_lowercased(client):
	# Email local parts aren't case-sensitive in practice, so "PearGor" and
	# "peargor" have to collapse to one row or only one of them ever matches.
	body = client.post(
		"/api/subjects/",
		json={"name": "Pear", "handles": ["PearGor"]},
	).json()

	assert body["handles"] == ["peargor"]


def test_handles_are_stripped(client):
	body = client.post(
		"/api/subjects/",
		json={"name": "Pear", "handles": ["  peargor  "]},
	).json()

	assert body["handles"] == ["peargor"]


def test_duplicate_handles_in_one_request_collapse(client):
	# Same handle twice is a typo, not a conflict — dedupe rather than 409.
	body = client.post(
		"/api/subjects/",
		json={"name": "Pear", "handles": ["peargor", "PEARGOR", " peargor "]},
	).json()

	assert body["handles"] == ["peargor"]


def test_handle_taken_by_another_subject_409s(client):
	client.post("/api/subjects/", json={"name": "Pear", "handles": ["peargor"]})

	response = client.post(
		"/api/subjects/",
		json={"name": "Someone Else", "handles": ["peargor"]},
	)

	assert response.status_code == 409
	# and the second subject was not created
	assert [s["name"] for s in client.get("/api/subjects/").json()] == ["Pear"]


def test_handle_clash_is_caught_on_create_despite_null_id(client):
	# Regression: the clash query excludes the subject's own rows, but a subject
	# being created has no id yet and `subject_id != NULL` is never true in SQL.
	# Applied unconditionally, that filter matches nothing and the duplicate slips
	# through to an IntegrityError at commit — a 500 instead of this 409.
	client.post("/api/subjects/", json={"name": "First", "handles": ["shared"]})

	response = client.post("/api/subjects/", json={"name": "Second", "handles": ["shared"]})

	assert response.status_code == 409


def test_patch_sets_handles(client, subject):
	response = client.patch(
		f"/api/subjects/{subject['id']}",
		json={"handles": ["denji", "chainsawman"]},
	)

	assert response.status_code == 200
	assert response.json()["handles"] == ["chainsawman", "denji"]


def test_patch_keeping_own_handle_is_not_a_conflict(client, subject):
	# Re-sending a handle the subject already owns must not collide with itself.
	client.patch(f"/api/subjects/{subject['id']}", json={"handles": ["denji"]})

	response = client.patch(
		f"/api/subjects/{subject['id']}",
		json={"handles": ["denji", "denji2"]},
	)

	assert response.status_code == 200
	assert response.json()["handles"] == ["denji", "denji2"]


def test_patch_with_empty_list_clears_handles(client, subject):
	client.patch(f"/api/subjects/{subject['id']}", json={"handles": ["denji"]})

	response = client.patch(f"/api/subjects/{subject['id']}", json={"handles": []})

	assert response.status_code == 200
	assert response.json()["handles"] == []


def test_patch_with_omitted_handles_leaves_them_alone(client, subject):
	client.patch(f"/api/subjects/{subject['id']}", json={"handles": ["denji"]})

	# Same exclude_unset distinction the category field relies on: an empty body
	# must not be read as "clear the handles".
	response = client.patch(f"/api/subjects/{subject['id']}", json={"category_name": None})

	assert response.status_code == 200
	assert response.json()["handles"] == ["denji"]


def test_patch_handle_taken_by_another_subject_409s(client, subject):
	client.post("/api/subjects/", json={"name": "Pear", "handles": ["peargor"]})

	response = client.patch(f"/api/subjects/{subject['id']}", json={"handles": ["peargor"]})

	assert response.status_code == 409


def test_deleting_a_subject_frees_its_handles(client):
	# delete-orphan in Python is the only thing doing this — SQLite's foreign keys
	# are off, so a stranded handle row would keep the name reserved forever and
	# keep matching mail to a subject that no longer exists.
	created = client.post(
		"/api/subjects/", json={"name": "Pear", "handles": ["peargor"]}
	).json()

	assert client.delete(f"/api/subjects/{created['id']}").status_code == 204

	reused = client.post("/api/subjects/", json={"name": "New Owner", "handles": ["peargor"]})
	assert reused.status_code == 201


def test_handles_survive_a_backup_round_trip(client):
	# SubjectBackup lists its fields explicitly, so handles are exactly the kind of
	# thing that gets silently dropped from an export and lost on restore.
	client.post("/api/subjects/", json={"name": "Pear", "handles": ["peargor"]})
	document = client.get("/api/backup/export").json()

	assert document["subjects"][0]["handles"] == ["peargor"]

	result = client.post("/api/backup/import?mode=replace", json=document)

	assert result.status_code == 200
	assert client.get("/api/subjects/").json()[0]["handles"] == ["peargor"]


def test_import_rejects_two_subjects_sharing_a_handle(client):
	document = {
		"version": 1,
		"subjects": [
			{"name": "One", "handles": ["shared"]},
			{"name": "Two", "handles": ["shared"]},
		],
	}

	response = client.post("/api/backup/import?mode=replace", json=document)

	# Only the status is asserted, matching the other import-failure tests. The
	# fixture shares one never-closed session across requests and leaves autoflush
	# on, so a pending row becomes visible to the next query even though nothing
	# was committed — this setup cannot honestly test the rollback.
	assert response.status_code == 400
