"""Notification-mail polling: parsing, matching, and the unread badge.

The IMAP half is swapped out via dependency_overrides, exactly the way get_db is
— so everything here exercises the real matching logic without a mail server
existing anywhere. `fetch_unseen` itself is the only untested part, and it is
deliberately thin for that reason.
"""
from datetime import datetime

import pytest

from app.mail import IncomingMail, MailConfig, get_mail_config, get_mail_fetcher, parse_message
from app.main import app

# Fixed timestamps rather than utcnow(): the badge compares detected_at against
# last_checked, and two calls landing in the same microsecond would make these
# tests flaky for reasons that have nothing to do with the code.
EARLIER = datetime(2026, 8, 30, 7, 0, 0)


@pytest.fixture
def mailbox(client):
	"""A list standing in for the inbox. Append messages, then POST /api/mail/poll."""
	inbox: list[IncomingMail] = []

	app.dependency_overrides[get_mail_config] = lambda: MailConfig(
		host="imap.example.test", user="gather@example.test", password="secret"
	)
	app.dependency_overrides[get_mail_fetcher] = lambda: (lambda config: list(inbox))
	try:
		yield inbox
	finally:
		app.dependency_overrides.pop(get_mail_config, None)
		app.dependency_overrides.pop(get_mail_fetcher, None)


def message(sender, subject="August Character Poll", message_id=None, received_at=EARLIER):
	return IncomingMail(
		message_id=message_id or f"<{sender}/{subject}>",
		sender=sender,
		subject=subject,
		received_at=received_at,
	)


def patreon(client):
	"""A complete chain: platform with a known mail domain, subject, tracker.

	The tracker sends no rules, so it inherits the platform's domain as a starting
	"sender contains creator.patreon.com" rule.
	"""
	client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)
	client.post("/api/subjects/", json={"name": "Pear哥"})
	return client.post(
		"/api/trackers/",
		json={
			"subject_name": "Pear哥",
			"platform_name": "Patreon - Mail",
			"url": "https://patreon.com/peargor",
		},
	).json()


# ---- parsing ---------------------------------------------------------------

def test_parses_a_real_patreon_header():
	raw = (
		b"From: =?utf-8?B?UGVhcuWTpQ==?= <peargor@creator.patreon.com>\r\n"
		b"Reply-To: no-reply@creator.patreon.com\r\n"
		b"To: myigitaydin@example.test\r\n"
		b"Message-ID: <abc123@creator.patreon.com>\r\n"
		b"Subject: August Character Poll\r\n"
		b"Date: Sun, 30 Aug 2026 07:42:00 +0300\r\n"
		b"\r\nbody\r\n"
	)

	parsed = parse_message(raw)

	# The display name is dropped; rules match against the bare address.
	assert parsed.sender == "peargor@creator.patreon.com"
	assert parsed.subject == "August Character Poll"
	assert parsed.message_id == "<abc123@creator.patreon.com>"
	# +03:00 converted to UTC, not merely stripped.
	assert parsed.received_at == datetime(2026, 8, 30, 4, 42, 0)


def test_decodes_an_encoded_subject():
	raw = (
		b"From: a@creator.patreon.com\r\n"
		b"Message-ID: <x@y>\r\n"
		b"Subject: =?utf-8?B?UGVhcuWTpQ==?=\r\n"
		b"\r\nbody\r\n"
	)

	assert parse_message(raw).subject == "Pear哥"


def test_sender_is_lowercased():
	raw = b"From: PearGor@Creator.Patreon.COM\r\nMessage-ID: <x@y>\r\n\r\nbody\r\n"

	assert parse_message(raw).sender == "peargor@creator.patreon.com"


def test_message_without_an_id_falls_back_to_a_content_hash():
	# Message-ID is the idempotency key, so something has to fill it rather than
	# the message being dropped.
	raw = b"From: a@creator.patreon.com\r\nSubject: Hi\r\n\r\nbody\r\n"

	assert parse_message(raw).message_id.startswith("sha256:")


def test_message_without_a_usable_sender_is_unparseable():
	assert parse_message(b"Subject: Hi\r\n\r\nbody\r\n") is None


# ---- matching --------------------------------------------------------------

def test_poll_records_an_update(client, mailbox):
	tracker = patreon(client)
	mailbox.append(message("peargor@creator.patreon.com"))

	body = client.post("/api/mail/poll").json()

	assert body == {"fetched": 1, "recorded": 1, "duplicates": 0, "unmatched": 0}
	updates = client.get(f"/api/trackers/{tracker['id']}/updates").json()
	assert [u["summary"] for u in updates] == ["August Character Poll"]


def test_matching_ignores_sender_case(client, mailbox):
	patreon(client)
	mailbox.append(message("PearGor@creator.patreon.com"))

	assert client.post("/api/mail/poll").json()["recorded"] == 1


def test_polling_twice_records_nothing_new(client, mailbox):
	# The unique external_ref is what makes re-polling safe, which matters because
	# fetch marks mail \Seen only after a successful pass.
	patreon(client)
	mailbox.append(message("peargor@creator.patreon.com"))
	client.post("/api/mail/poll")

	body = client.post("/api/mail/poll").json()

	assert body["recorded"] == 0
	assert body["duplicates"] == 1


def test_the_same_message_twice_in_one_batch_collides_with_itself(client, mailbox):
	# Regression: autoflush is off, so a row added moments ago is invisible to
	# db.query(). Without the in-pass `seen` set both copies pass the existence
	# check and then break the unique constraint at commit, failing the whole poll.
	patreon(client)
	duplicate = message("peargor@creator.patreon.com", message_id="<same@id>")
	mailbox.extend([duplicate, duplicate])

	body = client.post("/api/mail/poll").json()

	assert body["recorded"] == 1
	assert body["duplicates"] == 1


def test_mail_no_rule_claims_is_recorded_as_unmatched(client, mailbox):
	patreon(client)
	mailbox.append(message("someone@unknown.test"))

	assert client.post("/api/mail/poll").json()["unmatched"] == 1

	rejects = client.get("/api/mail/unmatched").json()
	assert "match rules" in rejects[0]["reason"]
	assert rejects[0]["sender"] == "someone@unknown.test"


def test_a_tracker_with_no_rules_never_matches(client, mailbox, subject, platform):
	# all([]) is True, so without an explicit guard every rule-less tracker would
	# claim every message the moment mail started arriving.
	client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": platform["name"],
			"url": "https://example.test/a",
		},
	)
	mailbox.append(message("anyone@anywhere.test"))

	assert client.post("/api/mail/poll").json()["recorded"] == 0


def test_all_of_a_trackers_rules_must_hold(client, mailbox, subject):
	# The AND is what makes not_contains useful: catch this sender, except digests.
	client.post("/api/platforms/", json={"name": "Patreon - Mail"})
	tracker = client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Patreon - Mail",
			"rules": [
				{"field": "sender", "operator": "contains", "value": "creator.patreon.com"},
				{"field": "subject", "operator": "not_contains", "value": "weekly digest"},
			],
		},
	).json()

	mailbox.append(message("x@creator.patreon.com", subject="New post"))
	mailbox.append(message("x@creator.patreon.com", subject="Your weekly digest"))

	body = client.post("/api/mail/poll").json()

	assert body["recorded"] == 1
	assert body["unmatched"] == 1
	summaries = [u["summary"] for u in client.get(f"/api/trackers/{tracker['id']}/updates").json()]
	assert summaries == ["New post"]


def test_a_subject_line_rule_matches_a_generic_sender(client, mailbox, subject):
	# The case the old handle model could not express at all: one shared sender
	# address, with the artist named in the subject line.
	client.post("/api/platforms/", json={"name": "Pixiv - Mail"})
	client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Pixiv - Mail",
			"rules": [{"field": "subject", "operator": "contains", "value": "peargor"}],
		},
	)

	mailbox.append(message("no-reply@pixiv.net", subject="peargor posted a new work"))

	assert client.post("/api/mail/poll").json()["recorded"] == 1


def test_one_message_can_land_on_several_trackers(client, mailbox, subject):
	# Two artists genuinely can appear in one notification; that's information
	# rather than an error, so it records on both.
	client.post("/api/platforms/", json={"name": "Pixiv - Mail"})
	client.post("/api/subjects/", json={"name": "Other"})
	for name, needle in [(subject["name"], "peargor"), ("Other", "nyantcha")]:
		client.post(
			"/api/trackers/",
			json={
				"subject_name": name,
				"platform_name": "Pixiv - Mail",
				"rules": [{"field": "subject", "operator": "contains", "value": needle}],
			},
		)

	mailbox.append(message("no-reply@pixiv.net", subject="peargor and nyantcha posted"))

	assert client.post("/api/mail/poll").json()["recorded"] == 1
	counts = [t["unread_count"] for t in client.get("/api/trackers/").json()]
	assert sorted(counts) == [1, 1]


def test_rule_matching_ignores_case(client, mailbox, subject):
	client.post("/api/platforms/", json={"name": "Pixiv - Mail"})
	client.post(
		"/api/trackers/",
		json={
			"subject_name": subject["name"],
			"platform_name": "Pixiv - Mail",
			"rules": [{"field": "subject", "operator": "contains", "value": "PearGor"}],
		},
	)

	mailbox.append(message("no-reply@pixiv.net", subject="peargor posted"))

	assert client.post("/api/mail/poll").json()["recorded"] == 1


def test_unmatched_mail_can_be_dismissed(client, mailbox):
	mailbox.append(message("someone@unknown.test"))
	client.post("/api/mail/poll")
	reject = client.get("/api/mail/unmatched").json()[0]

	assert client.delete(f"/api/mail/unmatched/{reject['id']}").status_code == 204
	assert client.get("/api/mail/unmatched").json() == []


def test_poll_without_configuration_503s(client, no_mail_env):
	# No `mailbox` fixture and no stored account, so there is no config at all.
	# no_mail_env matters: without it this passes only on a machine that happens
	# not to export ARTRACKER_MAIL_*, which stops being true the moment someone
	# actually configures the feature that way.
	response = client.post("/api/mail/poll")

	assert response.status_code == 503
	assert "ARTRACKER_MAIL_HOST" in response.json()["detail"]


# ---- the badge -------------------------------------------------------------

def test_unread_count_appears_on_the_tracker(client, mailbox):
	patreon(client)
	mailbox.append(message("peargor@creator.patreon.com"))
	client.post("/api/mail/poll")

	assert client.get("/api/trackers/").json()[0]["unread_count"] == 1


def test_opening_the_tracker_clears_the_badge(client, mailbox):
	# No separate "last seen" column: Open already stamps last_checked, and the
	# badge counts updates newer than it.
	tracker = patreon(client)
	mailbox.append(message("peargor@creator.patreon.com"))
	client.post("/api/mail/poll")

	client.post(f"/api/trackers/{tracker['id']}/check")

	assert client.get("/api/trackers/").json()[0]["unread_count"] == 0


def test_undoing_a_check_brings_the_badge_back(client, mailbox):
	tracker = patreon(client)
	mailbox.append(message("peargor@creator.patreon.com"))
	client.post("/api/mail/poll")
	client.post(f"/api/trackers/{tracker['id']}/check")

	# The existing undo — last_checked is writable, and null means "never checked".
	client.patch(f"/api/trackers/{tracker['id']}", json={"last_checked": None})

	assert client.get("/api/trackers/").json()[0]["unread_count"] == 1


def test_deleting_a_tracker_takes_its_updates_with_it(client, mailbox):
	# Otherwise the orphaned rows keep their unique external_ref reserved and the
	# same mail can never be recorded again.
	tracker = patreon(client)
	mailbox.append(message("peargor@creator.patreon.com", message_id="<keep@me>"))
	client.post("/api/mail/poll")

	client.delete(f"/api/trackers/{tracker['id']}")
	rebuilt = patreon(client)
	body = client.post("/api/mail/poll").json()

	assert body["recorded"] == 1
	assert len(client.get(f"/api/trackers/{rebuilt['id']}/updates").json()) == 1


# ---- stored mailbox credentials --------------------------------------------

import json as _json

from app.mail import resolve_mail_config
from app.models import MailAccount

MAILBOX_ENV = ("ARTRACKER_MAIL_HOST", "ARTRACKER_MAIL_USER", "ARTRACKER_MAIL_PASSWORD")


@pytest.fixture
def no_mail_env(monkeypatch):
	"""Nothing configured through the environment, whatever the shell has set."""
	for name in MAILBOX_ENV:
		monkeypatch.delenv(name, raising=False)


def save_account(client, **overrides):
	payload = {
		"host": "imap.example.test",
		"username": "gather@example.test",
		"password": "hunter2",
		**overrides,
	}
	return client.put("/api/mail/account", json=payload)


def test_mailbox_starts_unset(client, no_mail_env):
	body = client.get("/api/mail/account").json()

	assert body["source"] == "unset"
	assert body["has_password"] is False


def test_saving_the_mailbox(client, no_mail_env):
	response = save_account(client)

	assert response.status_code == 200
	assert response.json()["source"] == "database"
	assert response.json()["has_password"] is True


def test_the_password_is_never_returned(client, no_mail_env):
	# The whole reason MailAccountOut omits it: every endpoint here is
	# unauthenticated, so anything on a response model is public.
	save_account(client)

	body = client.get("/api/mail/account").json()

	assert "password" not in body
	assert "hunter2" not in _json.dumps(body)


def test_the_password_is_not_in_the_backup(client, no_mail_env):
	# The export is a file that gets downloaded and passed around.
	save_account(client)

	document = client.get("/api/backup/export").json()

	assert "hunter2" not in _json.dumps(document)


def test_the_first_save_requires_a_password(client, no_mail_env):
	response = client.put(
		"/api/mail/account",
		json={"host": "imap.example.test", "username": "gather@example.test"},
	)

	assert response.status_code == 400


def test_editing_without_a_password_keeps_the_stored_one(client, db_session, no_mail_env):
	# The UI never receives the password back, so it has nothing to resend when
	# only the host changes. Without this, editing any field wipes the credential.
	save_account(client)

	save_account(client, host="imap2.example.test", password=None)

	account = db_session.query(MailAccount).first()
	assert account.host == "imap2.example.test"
	assert account.password == "hunter2"


def test_an_empty_password_is_rejected_rather_than_wiping(client, no_mail_env):
	save_account(client)

	response = save_account(client, password="")

	assert response.status_code == 422


def test_the_stored_mailbox_beats_the_environment(client, db_session, monkeypatch):
	# Otherwise saving credentials in the UI appears to do nothing on a container
	# that already sets the variables.
	monkeypatch.setenv("ARTRACKER_MAIL_HOST", "env.example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_USER", "env@example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_PASSWORD", "envpass")
	save_account(client, host="db.example.test")

	assert resolve_mail_config(db_session).host == "db.example.test"


def test_the_environment_is_used_when_nothing_is_stored(db_session, monkeypatch):
	# Keeps existing Docker deployments working untouched.
	monkeypatch.setenv("ARTRACKER_MAIL_HOST", "env.example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_USER", "env@example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_PASSWORD", "envpass")

	assert resolve_mail_config(db_session).host == "env.example.test"


def test_clearing_the_mailbox_falls_back_to_the_environment(client, db_session, monkeypatch):
	monkeypatch.setenv("ARTRACKER_MAIL_HOST", "env.example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_USER", "env@example.test")
	monkeypatch.setenv("ARTRACKER_MAIL_PASSWORD", "envpass")
	save_account(client, host="db.example.test")

	assert client.delete("/api/mail/account").status_code == 204

	assert resolve_mail_config(db_session).host == "env.example.test"


def test_clearing_a_mailbox_that_was_never_set_404s(client, no_mail_env):
	assert client.delete("/api/mail/account").status_code == 404


def test_a_saved_mailbox_makes_polling_possible(client, db_session, no_mail_env):
	# Without a stored account and without the env vars, /poll 503s. Saving one
	# is what turns the feature on.
	assert client.post("/api/mail/poll").status_code == 503

	save_account(client)

	# Now it gets as far as trying to reach the mailbox, which fails at connect
	# rather than at configuration.
	assert client.post("/api/mail/poll").status_code == 502
