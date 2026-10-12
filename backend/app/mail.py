import asyncio
import email
import hashlib
import imaplib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from fastapi import Depends
from sqlalchemy.orm import Session, selectinload

from .database import get_db
from .models import (
	MailAccount,
	MatchRule,
	PollSchedule,
	Tracker,
	UnmatchedMail,
	Update,
	utcnow,
)


class MailError(RuntimeError):
	"""Mailbox unreadable: network, auth or protocol failure."""


@dataclass(frozen=True)
class MailConfig:
	host: str
	user: str
	password: str
	port: int = 993
	mailbox: str = "INBOX"


def mail_config_from_env() -> MailConfig | None:
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
	message_id: str
	sender: str  # bare address, lowercased — no display name
	subject: str
	received_at: datetime  # naive UTC, like everything else in the DB


@dataclass(frozen=True)
class MailBatch:
	messages: list[IncomingMail]
	uid_validity: str | None
	highest_uid: int | None


def _decode(value: str | None) -> str:
	if not value:
		return ""
	try:
		return str(make_header(decode_header(value))).strip()
	except (UnicodeDecodeError, LookupError, ValueError):
		return value.strip()


def parse_message(raw: bytes) -> IncomingMail | None:
	message = email.message_from_bytes(raw)

	_, address = parseaddr(message.get("From", ""))
	address = address.strip().lower()
	if "@" not in address:
		return None

	# Fallback key for mail without a Message-ID.
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


def fetch_new(
	config: MailConfig,
	last_uid: int | None = None,
	uid_validity: str | None = None,
) -> MailBatch:
	# UIDs are scoped to UIDVALIDITY; if it changes, rescan and let Message-ID dedupe.
	messages: list[IncomingMail] = []
	current_validity: str | None = None
	highest_uid: int | None = None

	try:
		with imaplib.IMAP4_SSL(config.host, config.port) as imap:
			imap.login(config.user, config.password)
			status, _ = imap.select(config.mailbox)
			if status != "OK":
				raise MailError(f"Could not select mailbox '{config.mailbox}'")

			_, validity_data = imap.response("UIDVALIDITY")
			if validity_data and validity_data[0] is not None:
				raw_validity = validity_data[0]
				current_validity = (
					raw_validity.decode("ascii", errors="replace")
					if isinstance(raw_validity, bytes)
					else str(raw_validity)
				)

			cursor = last_uid or 0
			if uid_validity != current_validity:
				cursor = 0

			status, data = imap.uid("search", None, "ALL")
			if status != "OK" or not data or not data[0]:
				if status != "OK":
					raise MailError("Could not search the mailbox")
				return MailBatch(messages, current_validity, None)

			uids = sorted(int(value) for value in data[0].split())
			new_uids = [uid for uid in uids if uid > cursor]
			highest_uid = max(new_uids, default=None)

			for uid in new_uids:
				status, payload = imap.uid(
					"fetch",
					str(uid),
					"(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
				)
				if status != "OK" or not payload:
					raise MailError(f"Could not fetch message UID {uid}")
				for part in payload:
					if isinstance(part, tuple) and len(part) > 1:
						if parsed := parse_message(part[1]):
							messages.append(parsed)
	except (imaplib.IMAP4.error, OSError, ValueError) as error:
		raise MailError(str(error)) from error

	return MailBatch(messages, current_validity, highest_uid)


def resolve_mail_config(db: Session) -> MailConfig | None:
	# A stored account wins over the environment.
	account = db.query(MailAccount).first()
	if account and account.host and account.username and account.password:
		return MailConfig(
			host=account.host,
			user=account.username,
			password=account.password,
			port=account.port,
			mailbox=account.mailbox or "INBOX",
		)
	return mail_config_from_env()


def get_mail_config(db: Session = Depends(get_db)) -> MailConfig | None:
	return resolve_mail_config(db)


def get_mail_fetcher():
	return fetch_new


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


def rule_matches(rule: MatchRule, mail: IncomingMail) -> bool:
	haystack = (mail.sender if rule.field == "sender" else mail.subject or "").lower()
	needle = (rule.value or "").lower()

	if rule.operator == "contains":
		return needle in haystack
	if rule.operator == "not_contains":
		return needle not in haystack
	if rule.operator == "equals":
		return haystack == needle
	if rule.operator == "not_equals":
		return haystack != needle
	return False


def matching_trackers(db: Session, mail: IncomingMail) -> list[Tracker]:
	# A tracker with no rules, or only negative ones, never matches.
	trackers = db.query(Tracker).options(selectinload(Tracker.rules)).all()
	return [
		tracker
		for tracker in trackers
		if tracker.rules
		and any(rule.operator in ("contains", "equals") for rule in tracker.rules)
		and all(rule_matches(rule, mail) for rule in tracker.rules)
	]


def record_message(db: Session, mail: IncomingMail, seen: set[str]) -> str:
	# `seen` spans the batch: autoflush=False hides rows added earlier in it.
	if mail.message_id in seen:
		return "duplicate"
	seen.add(mail.message_id)

	already_rejected = (
		db.query(UnmatchedMail).filter(UnmatchedMail.external_ref == mail.message_id).first()
	)
	if already_rejected:
		return "duplicate"

	matches = matching_trackers(db, mail)
	if not matches:
		_reject(db, mail, "No tracker's match rules applied to this message")
		return "unmatched"

	# Scoped per tracker, since the same message can land on several.
	refs = [f"{tracker.id}:{mail.message_id}" for tracker in matches]
	existing = {
		row.external_ref
		for row in db.query(Update).filter(Update.external_ref.in_(refs)).all()
	}
	if len(existing) == len(refs):
		return "duplicate"

	for tracker, ref in zip(matches, refs):
		if ref in existing:
			continue
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

	return outcome


def record_batch(db: Session, schedule: PollSchedule, batch: MailBatch) -> PollOutcome:
	outcome = record_messages(db, batch.messages)

	if schedule.uid_validity != batch.uid_validity:
		schedule.last_uid = None
	schedule.uid_validity = batch.uid_validity
	if batch.highest_uid is not None:
		schedule.last_uid = batch.highest_uid

	return outcome



# The loop checks whether a run is due rather than sleeping the whole interval.
TICK_SECONDS = 60

MIN_INTERVAL_MINUTES = 5

logger = logging.getLogger(__name__)


def run_one_poll(db: Session, schedule: PollSchedule) -> str:
	# Blocking (imaplib); run it in a thread from async code.
	config = resolve_mail_config(db)
	if config is None:
		return "No mailbox is configured"

	batch = fetch_new(config, schedule.last_uid, schedule.uid_validity)
	outcome = record_batch(db, schedule, batch)
	db.commit()
	return (
		f"{len(batch.messages)} read, {outcome.recorded} recorded,"
		f" {outcome.duplicates} already seen, {outcome.unmatched} unmatched"
	)


def _due(schedule: PollSchedule, now: datetime) -> bool:
	if not schedule.enabled:
		return False
	if schedule.last_run_at is None:
		return True
	interval = max(schedule.interval_minutes or 0, MIN_INTERVAL_MINUTES)
	return now - schedule.last_run_at >= timedelta(minutes=interval)


def poll_if_due(session_factory) -> str | None:
	# Opens its own session: there's no request to borrow one from.
	with session_factory() as db:
		schedule = db.query(PollSchedule).first()
		if schedule is None or not _due(schedule, utcnow()):
			return None

		# Stamped before the work so a hung poll isn't restarted every tick.
		schedule.last_run_at = utcnow()
		db.commit()

		try:
			result = run_one_poll(db, schedule)
		except MailError as error:
			result = f"Failed: {error}"
		except Exception as error:  # noqa: BLE001 - see below
			# Broad on purpose: nothing above this loop would catch it.
			logger.exception("Scheduled mail poll failed")
			result = f"Failed: {error}"

		schedule.last_result = result[:500]
		db.commit()
		return result


async def poll_forever(session_factory) -> None:
	while True:
		try:
			await asyncio.to_thread(poll_if_due, session_factory)
		except asyncio.CancelledError:
			raise
		except Exception:  # noqa: BLE001
			logger.exception("Mail poller tick failed")

		await asyncio.sleep(TICK_SECONDS)
