"""Example tests — the pattern to copy for the rest.

Run with:  .venv/bin/pytest        (from backend/)
"""


def test_create_subject(client):
	# `client` is the fixture from conftest.py — pytest passes it in because
	# the parameter is named `client`. Same idea as Depends(get_db).
	response = client.post("/api/subjects/", json={"name": "Denji"})

	assert response.status_code == 201
	assert response.json()["name"] == "Denji"


def test_duplicate_subject_is_rejected(client):
	client.post("/api/subjects/", json={"name": "Denji"})
	response = client.post("/api/subjects/", json={"name": "Denji"})

	assert response.status_code == 409


def test_subjects_start_empty(client):
	# Proof the DB really is fresh per test: the subject created in the tests
	# above is not here. If this fails, the fixtures are leaking state.
	response = client.get("/api/subjects/")

	assert response.status_code == 200
	assert response.json() == []


def test_subjects_listed_alphabetically(client):
	for name in ["Power", "Denji", "Makima"]:
		client.post("/api/subjects/", json={"name": name})

	response = client.get("/api/subjects/")

	assert [s["name"] for s in response.json()] == ["Denji", "Makima", "Power"]


def test_delete_unused_subject(client, subject):
	response = client.delete(f"/api/subjects/{subject['id']}")

	assert response.status_code == 204
	assert client.get("/api/subjects/").json() == []


def test_delete_missing_subject_404s(client):
	response = client.delete("/api/subjects/999999")

	assert response.status_code == 404


def test_cannot_delete_subject_still_in_use(client, subject, platform):
	# The guard that stands in for SQLite's disabled foreign keys.
	client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"url": "https://example.test/a",
		},
	)

	response = client.delete(f"/api/subjects/{subject['id']}")

	assert response.status_code == 409
	assert "tracker" in response.json()["detail"].lower()
	assert len(client.get("/api/subjects/").json()) == 1


def test_create_rejects_oversized_name(client):
	assert client.post("/api/subjects/", json={"name": "A" * 100_000}).status_code == 422


def test_create_rejects_whitespace_only_name(client):
	assert client.post("/api/subjects/", json={"name": "   "}).status_code == 422


def test_name_is_stripped(client):
	body = client.post("/api/subjects/", json={"name": "  Padded  "}).json()

	assert body["name"] == "Padded"


def test_subject_has_no_category_by_default(client, subject):
	assert subject["category_name"] is None


def test_create_subject_with_category(client, category):
	response = client.post(
		"/api/subjects/",
		json={"name": "Denji", "category_name": category["name"]},
	)

	assert response.status_code == 201
	assert response.json()["category_name"] == "Character"


def test_create_subject_with_unknown_category_400s(client):
	response = client.post(
		"/api/subjects/",
		json={"name": "Denji", "category_name": "Nope"},
	)

	assert response.status_code == 400
	# and nothing was created
	assert client.get("/api/subjects/").json() == []


def test_patch_assigns_category(client, subject, category):
	response = client.patch(
		f"/api/subjects/{subject['id']}",
		json={"category_name": category["name"]},
	)

	assert response.status_code == 200
	assert response.json()["category_name"] == "Character"
	# and it stuck
	assert client.get("/api/subjects/").json()[0]["category_name"] == "Character"


def test_patch_with_null_clears_category(client, subject, category):
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})

	response = client.patch(f"/api/subjects/{subject['id']}", json={"category_name": None})

	assert response.status_code == 200
	assert response.json()["category_name"] is None


def test_patch_with_omitted_field_leaves_category_alone(client, subject, category):
	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": category["name"]})

	# An empty body is not the same as {"category_name": null} — exclude_unset
	# is what keeps those two apart.
	response = client.patch(f"/api/subjects/{subject['id']}", json={})

	assert response.status_code == 200
	assert response.json()["category_name"] == "Character"


def test_patch_unknown_category_400s(client, subject):
	response = client.patch(
		f"/api/subjects/{subject['id']}",
		json={"category_name": "Nope"},
	)

	assert response.status_code == 400


def test_patch_missing_subject_404s(client):
	response = client.patch("/api/subjects/999999", json={"category_name": None})

	assert response.status_code == 404
