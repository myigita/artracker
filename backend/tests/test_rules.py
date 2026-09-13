"""Match rules on trackers.

These replaced subject handles. The reason is in test_mail.py — a handle could
only ever be the sender's local part, so a platform that mails from one generic
address and names the artist in the subject line was impossible to express.
Here we only care that the rules themselves round-trip properly.
"""

SENDER_RULE = {"field": "sender", "operator": "contains", "value": "creator.patreon.com"}
SUBJECT_RULE = {"field": "subject", "operator": "not_contains", "value": "digest"}
POSITIVE_SUBJECT_RULE = {"field": "subject", "operator": "contains", "value": "peargor"}


def make(client, subject, platform, **extra):
	payload = {
		"subject_name": subject["name"],
		"platform_name": platform["name"],
		"url": "https://example.test/a",
	}
	payload.update(extra)
	return client.post("/api/trackers/", json=payload)


def test_a_tracker_starts_with_no_rules(client, subject, platform):
	assert make(client, subject, platform).json()["rules"] == []


def test_rules_can_be_set_at_creation(client, subject, platform):
	body = make(client, subject, platform, rules=[SENDER_RULE, SUBJECT_RULE]).json()

	assert len(body["rules"]) == 2
	assert {r["field"] for r in body["rules"]} == {"sender", "subject"}


def test_patch_replaces_the_rules(client, subject, platform):
	created = make(client, subject, platform, rules=[SENDER_RULE]).json()

	body = client.patch(
		f"/api/trackers/{created['id']}", json={"rules": [POSITIVE_SUBJECT_RULE]}
	).json()

	assert [r["value"] for r in body["rules"]] == ["peargor"]


def test_negative_rules_cannot_match_without_a_positive_rule(client, subject, platform):
	response = make(client, subject, platform, rules=[SUBJECT_RULE])

	assert response.status_code == 400
	assert "positive" in response.json()["detail"]


def test_patch_without_rules_leaves_them_alone(client, subject, platform):
	# Same exclude_unset distinction every other field relies on.
	created = make(client, subject, platform, rules=[SENDER_RULE]).json()

	body = client.patch(f"/api/trackers/{created['id']}", json={"name": "Renamed"}).json()

	assert len(body["rules"]) == 1
	assert body["name"] == "Renamed"


def test_resending_an_unchanged_rule_is_not_an_error(client, subject, platform):
	"""Regression in shape, not in kind.

	The handles version reassigned the whole collection, which made SQLAlchemy
	delete every row and insert every row with no guaranteed ordering — so a value
	re-sent unchanged collided with itself. _set_rules touches only the difference.
	"""
	created = make(client, subject, platform, rules=[SENDER_RULE]).json()

	response = client.patch(
		f"/api/trackers/{created['id']}", json={"rules": [SENDER_RULE, SUBJECT_RULE]}
	)

	assert response.status_code == 200
	assert len(response.json()["rules"]) == 2


def test_duplicate_rules_in_one_request_collapse(client, subject, platform):
	body = make(client, subject, platform, rules=[SENDER_RULE, dict(SENDER_RULE)]).json()

	assert len(body["rules"]) == 1


def test_rule_values_are_stripped(client, subject, platform):
	body = make(
		client, subject, platform,
		rules=[{"field": "sender", "operator": "contains", "value": "  patreon.com  "}],
	).json()

	assert body["rules"][0]["value"] == "patreon.com"


def test_an_unknown_field_is_rejected(client, subject, platform):
	# body isn't an option yet — the enum is what keeps that honest.
	response = make(
		client, subject, platform,
		rules=[{"field": "body", "operator": "contains", "value": "x"}],
	)

	assert response.status_code == 422


def test_an_unknown_operator_is_rejected(client, subject, platform):
	response = make(
		client, subject, platform,
		rules=[{"field": "sender", "operator": "regex", "value": "x"}],
	)

	assert response.status_code == 422


def test_a_blank_rule_value_is_rejected(client, subject, platform):
	response = make(
		client, subject, platform,
		rules=[{"field": "sender", "operator": "contains", "value": "   "}],
	)

	assert response.status_code == 422


def test_deleting_a_tracker_takes_its_rules_with_it(client, subject, platform, db_session):
	from app.models import MatchRule

	created = make(client, subject, platform, rules=[SENDER_RULE, SUBJECT_RULE]).json()

	client.delete(f"/api/trackers/{created['id']}")

	assert db_session.query(MatchRule).count() == 0


def test_rules_survive_a_backup_round_trip(client, subject, platform):
	# Configuration, not derived data — an export that dropped them would restore
	# a database that silently matches nothing.
	make(client, subject, platform, rules=[SENDER_RULE, SUBJECT_RULE])
	document = client.get("/api/backup/export").json()

	assert len(document["trackers"][0]["rules"]) == 2

	assert client.post("/api/backup/import?mode=replace", json=document).status_code == 200

	restored = client.get("/api/trackers/").json()[0]
	assert {r["value"] for r in restored["rules"]} == {"creator.patreon.com", "digest"}
