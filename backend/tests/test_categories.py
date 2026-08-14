"""Category endpoints. Same shape as subjects and platforms, except the delete
guard counts *subjects* rather than trackers."""


def test_create_category(client):
	response = client.post("/api/categories/", json={"name": "Character"})

	assert response.status_code == 201
	assert response.json()["name"] == "Character"
	assert response.json()["id"] is not None


def test_duplicate_category_is_rejected(client):
	client.post("/api/categories/", json={"name": "Character"})
	response = client.post("/api/categories/", json={"name": "Character"})

	assert response.status_code == 409


def test_categories_listed_alphabetically(client):
	for name in ["Studio", "Artist", "Character"]:
		client.post("/api/categories/", json={"name": name})

	response = client.get("/api/categories/")

	assert response.status_code == 200
	assert [c["name"] for c in response.json()] == ["Artist", "Character", "Studio"]


def test_delete_unused_category(client, category):
	response = client.delete(f"/api/categories/{category['id']}")

	assert response.status_code == 204
	assert client.get("/api/categories/").json() == []


def test_delete_missing_category_404s(client):
	response = client.delete("/api/categories/999999")

	assert response.status_code == 404


def test_cannot_delete_category_still_in_use(client, category):
	# SQLite isn't enforcing the foreign key, so this guard is the only thing
	# stopping a subject from pointing at a category id that no longer exists.
	client.post(
		"/api/subjects/",
		json={"name": "Denji", "category_name": category["name"]},
	)

	response = client.delete(f"/api/categories/{category['id']}")

	assert response.status_code == 409
	assert "subject" in response.json()["detail"].lower()
	assert len(client.get("/api/categories/").json()) == 1


def test_category_freed_by_reassignment_can_be_deleted(client, category):
	subject = client.post(
		"/api/subjects/",
		json={"name": "Denji", "category_name": category["name"]},
	).json()

	client.patch(f"/api/subjects/{subject['id']}", json={"category_name": None})

	assert client.delete(f"/api/categories/{category['id']}").status_code == 204


def test_create_rejects_whitespace_only_name(client):
	assert client.post("/api/categories/", json={"name": "   "}).status_code == 422
