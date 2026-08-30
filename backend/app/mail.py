"""Reading "they posted something" out of notification email.

Most of the platforms worth following can't be polled: Patreon, SubscribeStar,
Pixiv and X all need paid API access or a logged-in session. But they all send
mail, and mail is something we can read without asking anyone's permission.

The resolution chain is:

    sender domain  -> Platform.mail_domain
    sender local   -> SubjectHandle.handle -> Subject
    the two of them-> the Tracker joining that subject and platform

Anything that falls out of that chain is written to `unmatched_mail` rather than
dropped, because a poller that silently discards what it can't parse is
indistinguishable from a platform that went quiet.

Splitting `fetch_unseen` (talks IMAP) from `record_message` (pure database work)
is deliberate: the matching logic is the part with the bugs in it, and it is
testable without a mail server anywhere in sight.
"""
import email
import hashlib
import imaplib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy.orm import Session

from .models import (
	Platform,
	Subject,
	SubjectHandle,
	Tracker,
	UnmatchedMail,
	Update,
	normalize_handle,
	utcnow,
)


class MailError(RuntimeError):
	"""The mailbox could not be read — network, auth, or protocol failure.

	Exists so the route layer can turn a mail problem into a 502 without importing
	imaplib to catch its exceptions.
	"""


@dataclass(frozen=True)
class MailConfig:
	host: str
	user: str
	password: str
	port: int = 993
	mailbox: str = "INBOX"


def mail_config_from_env() -> MailConfig | None:
	"""Mailbox credentials, or None if the feature isn't configured.

	Environment only, never the database. Every endpoint here is unauthenticated,
	so a password in a table is one careless response-model field away from being
	served to anyone who can reach the app — and the backup export is a file that
	gets downloaded and passed around.
	"""
	host = os.getenv("ARTRACKER_MAIL_HOST")
	user = os.getenv("ARTRACKER_MAIL_USER")
	password = os.getenv("ARTRACKER_MAIL_PASSWORD")
	if not (host and user and password):
		return None

	return MailConfig(
		host=host,
		user=user,
		password=password,
		port=int(os.getenv("ARTRACKER_MAIL_PORT", "993")),
		mailbox=os.getenv("ARTRACKER_MAIL_MAILBOX", "INBOX"),
	)


@dataclass(frozen=True)
class IncomingMail:
	"""One message, reduced to the four things matching actually needs."""
	message_id: str
	sender: str  # bare address, lowercased — no display name
	subject: str
	received_at: datetime  # naive UTC, like everything else in the DB


def _decode(value: str | None) -> str:
	"""RFC 2047 header decoding.

	Subject lines carrying non-ASCII arrive base64- or quoted-printable-encoded
	(`=?utf-8?B?...?=`). Without this they'd be stored as that literal gibberish,
	which matters here because the subject is what gets shown as the update
	summary.
	"""
	if not value:
		return ""
	try:
		return str(make_header(decode_header(value))).strip()
	except (UnicodeDecodeError, LookupError, ValueError):
		# Malformed encoding in the wild is common enough not to be worth a
		# crash; the raw header is still more useful than nothing.
		return value.strip()


def parse_message(raw: bytes) -> IncomingMail | None:
	"""Turn a raw RFC822 message into an IncomingMail, or None if unusable."""
	message = email.message_from_bytes(raw)

	_, address = parseaddr(message.get("From", ""))
	address = address.strip().lower()
	if "@" not in address:
		return None

	# Message-ID is the idempotency key, so something has to fill it. A content
	# hash is a worse key than a real Message-ID — an identical resend would
	# collide with the original — but it beats dropping the message, and mail
	# without a Message-ID is rare enough not to optimise for.
	message_id = (message.get("Message-ID") or "").strip()
	if not message_id:
		message_id = "sha256:" + hashlib.sha256(raw).hexdigest()

	received_at = utcnow()
	if date_header := message.get("Date"):
		try:
			parsed = parsedate_to_datetime(date_header)
			if parsed is not None:
				received_at = (
					parsed.astimezone(timezone.utc).replace(tzinfo=None)
					if parsed.tzinfo
					else parsed
				)
		except (TypeError, ValueError):
			pass  # Unparseable Date, fall back to "now".

	return IncomingMail(
		message_id=message_id,
		sender=address,
		subject=_decode(message.get("Subject")),
		received_at=received_at,
	)


def fetch_unseen(config: MailConfig) -> list[IncomingMail]:
	"""Every unread message in the mailbox, parsed.

	Fetching with RFC822 marks messages \\Seen as a side effect, which is what
	stops the next poll re-reading them. The window that opens: if the process
	dies between the fetch and the database commit, those messages are marked read
	but never recorded, and are missed. Peeking instead and marking afterwards
	would close it, at the cost of holding the IMAP connection across the write.
	Not worth it here — the failure costs a missed badge, not data.
	"""
	messages: list[IncomingMail] = []

	try:
		with imaplib.IMAP4_SSL(config.host, config.port) as imap:
			imap.login(config.user, config.password)
			imap.select(config.mailbox)

			status, data = imap.search(None, "UNSEEN")
			if status != "OK" or not data or not data[0]:
				return messages

			for number in data[0].split():
				status, payload = imap.fetch(number, "(RFC822)")
				if status != "OK" or not payload:
					continue
				for part in payload:
					# imaplib returns a mix of tuples (the body) and bare bytes
					# (the flag echoes); only the tuples carry a message.
					if isinstance(part, tuple) and len(part) > 1:
						if parsed := parse_message(part[1]):
							messages.append(parsed)
	except (imaplib.IMAP4.error, OSError) as error:
		raise MailError(str(error)) from error

	return messages


def get_mail_config() -> MailConfig | None:
	"""Dependency wrapper around mail_config_from_env.

	Separate from the fetcher so a test can supply a dummy config without also
	having to fake the environment — the route checks the config before it ever
	calls the fetcher, so overriding only one of the two isn't enough.
	"""
	return mail_config_from_env()


def get_mail_fetcher():
	"""The callable the poll route uses to obtain messages.

	A dependency purely so tests can override it, exactly like get_db — otherwise
	every test of the matching logic would need a live IMAP server. Returns the
	function rather than calling it, so the route decides when to connect.
	"""
	return fetch_unseen


@dataclass
class PollOutcome:
	recorded: int = 0
	duplicates: int = 0
	unmatched: int = 0


def _reject(db: Session, mail: IncomingMail, reason: str) -> None:
	db.add(
		UnmatchedMail(
			external_ref=mail.message_id,
			sender=mail.sender,
			subject=mail.subject,
			reason=reason,
			received_at=mail.received_at,
		)
	)


def record_message(db: Session, mail: IncomingMail, seen: set[str]) -> str:
	"""Resolve one message to a tracker and record it.

	Returns "recorded", "duplicate" or "unmatched".

	`seen` collects the refs handled in this pass and is why it's a parameter
	rather than a local. SessionLocal sets autoflush=False, so a row added moments
	ago is invisible to db.query() until flush — two copies of the same Message-ID
	in one batch would both pass the existence check and then collide on the
	unique constraint at commit, failing the whole poll.
	"""
	ref = mail.message_id
	if ref in seen:
		return "duplicate"
	seen.add(ref)

	already_recorded = db.query(Update).filter(Update.external_ref == ref).first()
	already_rejected = db.query(UnmatchedMail).filter(UnmatchedMail.external_ref == ref).first()
	if already_recorded or already_rejected:
		return "duplicate"

	local, _, domain = mail.sender.partition("@")

	platform = db.query(Platform).filter(Platform.mail_domain == domain).first()
	if platform is None:
		_reject(db, mail, f"No platform is configured for the sender domain '{domain}'")
		return "unmatched"

	handle = (
		db.query(SubjectHandle)
		.filter(SubjectHandle.handle == normalize_handle(local))
		.first()
	)
	if handle is None:
		_reject(db, mail, f"No subject has the handle '{local}'")
		return "unmatched"

	tracker = (
		db.query(Tracker)
		.filter(Tracker.subject_id == handle.subject_id, Tracker.platform_id == platform.id)
		.first()
	)
	if tracker is None:
		subject = db.query(Subject).filter(Subject.id == handle.subject_id).first()
		name = subject.name if subject else handle.handle
		_reject(db, mail, f"'{name}' has no '{platform.name}' tracker")
		return "unmatched"

	db.add(
		Update(
			tracker_id=tracker.id,
			external_ref=ref,
			summary=mail.subject,
			detected_at=mail.received_at,
		)
	)
	return "recorded"


def record_messages(db: Session, messages: list[IncomingMail]) -> PollOutcome:
	"""Record a batch. Commits once, so a bad message can't half-apply a pass."""
	outcome = PollOutcome()
	seen: set[str] = set()

	for mail in messages:
		result = record_message(db, mail, seen)
		if result == "recorded":
			outcome.recorded += 1
		elif result == "duplicate":
			outcome.duplicates += 1
		else:
			outcome.unmatched += 1

	db.commit()
	return outcome
