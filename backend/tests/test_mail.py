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
	"""Platform, subject-with-handle and tracker — a complete resolution chain."""
	client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)
	client.post("/api/subjects/", json={"name": "Pear哥", "handles": ["peargor"]})
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

	# The display name is ignored entirely; the local part is the identifier.
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


def test_unknown_sender_domain_is_recorded_as_unmatched(client, mailbox):
	patreon(client)
	mailbox.append(message("someone@unknown.test"))

	assert client.post("/api/mail/poll").json()["unmatched"] == 1

	rejects = client.get("/api/mail/unmatched").json()
	assert "unknown.test" in rejects[0]["reason"]


def test_unknown_handle_is_recorded_as_unmatched(client, mailbox):
	patreon(client)
	mailbox.append(message("nobody@creator.patreon.com"))

	client.post("/api/mail/poll")

	rejects = client.get("/api/mail/unmatched").json()
	assert "nobody" in rejects[0]["reason"]


def test_subject_without_a_tracker_on_that_platform_is_unmatched(client, mailbox):
	# Handle resolves, platform resolves, but nothing joins them.
	client.post(
		"/api/platforms/",
		json={"name": "Patreon - Mail", "mail_domain": "creator.patreon.com"},
	)
	client.post("/api/subjects/", json={"name": "Pear哥", "handles": ["peargor"]})
	mailbox.append(message("peargor@creator.patreon.com"))

	client.post("/api/mail/poll")

	rejects = client.get("/api/mail/unmatched").json()
	assert "no 'Patreon - Mail' tracker" in rejects[0]["reason"]


def test_unmatched_mail_can_be_dismissed(client, mailbox):
	mailbox.append(message("someone@unknown.test"))
	client.post("/api/mail/poll")
	reject = client.get("/api/mail/unmatched").json()[0]

	assert client.delete(f"/api/mail/unmatched/{reject['id']}").status_code == 204
	assert client.get("/api/mail/unmatched").json() == []


def test_poll_without_configuration_503s(client):
	# No `mailbox` fixture, so the env-backed config is None.
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
