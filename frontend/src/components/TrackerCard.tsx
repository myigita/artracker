import { useState } from 'react';
import type { MatchRuleIn, Tracker, Update } from '../api';
import {
	checkTracker,
	deleteTracker,
	errorDetail,
	getTrackerUpdates,
	updateTracker,
} from '../api';
import MatchRulesEditor from './MatchRulesEditor';

type Props = {
	tracker: Tracker;
	onChecked: () => void;
	onDeleted: () => void;
	onUpdated: () => void;
};

const inputClass =
	'w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm ' +
	'text-[var(--text-h)] outline-none focus:border-[var(--accent-border)]';

const MINUTE = 60 * 1000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

function timeAgo(iso: string | null): string {
	if (iso === null) return 'never';

	const diff = Date.now() - new Date(iso).getTime();

	if (diff < MINUTE) return 'just now';
	if (diff < HOUR) return `${Math.floor(diff / MINUTE)}m ago`;
	if (diff < DAY) return `${Math.floor(diff / HOUR)}h ago`;
	return `${Math.floor(diff / DAY)}d ago`;
}

export default function TrackerCard({ tracker, onChecked, onDeleted, onUpdated }: Props) {
	const [editing, setEditing] = useState(false);
	const [name, setName] = useState(tracker.name);
	const [url, setUrl] = useState(tracker.url);
	const [description, setDescription] = useState(tracker.description ?? '');
	// Stripped of their ids: rules are replaced wholesale on save, so the server
	// assigns fresh ones and sending the old ones back would be meaningless.
	const [rules, setRules] = useState<MatchRuleIn[]>(() =>
		tracker.rules.map(({ field, operator, value }) => ({ field, operator, value })),
	);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	// The stamp to put back, captured before the check overwrote it. Wrapped in
	// an object because the value itself can legitimately be null ("never
	// checked"), which would otherwise be indistinguishable from "nothing to undo".
	const [undo, setUndo] = useState<{ previous: string | null } | null>(null);
	// Fetched on demand rather than with the list: the count comes down with every
	// tracker, but the summaries behind it are only wanted for the one card the
	// user actually asks about.
	const [updates, setUpdates] = useState<Update[] | null>(null);

	// Deliberately NOT on a timer. Opening a link moves focus to a new tab, so
	// the user is looking at the artist's page — possibly for minutes — before
	// they come back and realise they didn't mean to mark it checked. A short
	// countdown would always have expired by the moment the offer is wanted.
	// The offer lasts until it's used or the page is reloaded.

	function handleOpen() {
		// Read this BEFORE the check lands — afterwards it's already overwritten.
		const previous = tracker.last_checked;

		// Deliberately fire-and-forget: the link opens via the anchor's own
		// navigation, so a failed stamp must not block it. No undo is offered if
		// the stamp never happened.
		checkTracker(tracker.id)
			.then(() => {
				setUndo({ previous });
				onChecked();
			})
			.catch(() => {});
	}

	// A tracker on a mail-tracked platform can have no URL, so there's no link to
	// click and therefore nothing to stamp last_checked — which is what clears the
	// unread badge. This is that stamp on its own. Unlike handleOpen it reports
	// failure, because here nothing else happened to mask it.
	function handleMarkChecked() {
		const previous = tracker.last_checked;

		setError(null);
		checkTracker(tracker.id)
			.then(() => {
				setUndo({ previous });
				onChecked();
			})
			.catch(() => setError('Could not mark this as checked.'));
	}

	function handleUndo() {
		if (!undo) return;

		setError(null);
		updateTracker(tracker.id, { last_checked: undo.previous })
			.then(() => {
				setUndo(null);
				onUpdated();
			})
			.catch(() => setError('Could not undo that.'));
	}

	function toggleUpdates() {
		if (updates !== null) {
			setUpdates(null);
			return;
		}

		getTrackerUpdates(tracker.id)
			.then(setUpdates)
			.catch(() => setError('Could not load the updates for this tracker.'));
	}

	function handleDelete() {
		setError(null);
		deleteTracker(tracker.id)
			.then(() => onDeleted())
			.catch(() => setError('Could not delete this tracker.'));
	}

	function startEditing() {
		// Reset the fields from props each time, so a cancelled edit
		// doesn't leave stale text behind on the next open.
		setName(tracker.name);
		setUrl(tracker.url);
		setDescription(tracker.description ?? '');
		setRules(tracker.rules.map(({ field, operator, value }) => ({ field, operator, value })));
		setError(null);
		setEditing(true);
	}

	function handleSave(event: React.FormEvent) {
		event.preventDefault();
		if (!name.trim()) return;

		setSaving(true);
		setError(null);
		updateTracker(tracker.id, {
			name: name.trim(),
			// Sent even when blank. Whether this tracker may go without a URL
			// depends on its platform, which the card doesn't know — the backend
			// does, and it answers with a message worth showing.
			url: url.trim(),
			description: description.trim() || null,
			// Blank-valued rows are dropped rather than sent: an empty rule is a
			// half-finished thought, and the API rejects it with a schema error
			// that says nothing useful about which row is at fault.
			rules: rules
				.filter((rule) => rule.value.trim())
				.map((rule) => ({ ...rule, value: rule.value.trim() })),
		})
			.then(() => {
				setEditing(false);
				onUpdated();
			})
			.catch((err) => setError(errorDetail(err) ?? 'Could not save changes.'))
			.finally(() => setSaving(false));
	}

	if (editing) {
		return (
			<form
				onSubmit={handleSave}
				className="rounded-lg border border-[var(--accent-border)] p-4 shadow-sm"
			>
				<input
					autoFocus
					value={name}
					onChange={(e) => setName(e.target.value)}
					placeholder="Name"
					className={inputClass}
				/>
				<input
					value={url}
					onChange={(e) => setUrl(e.target.value)}
					placeholder="URL"
					className={`${inputClass} mt-2`}
				/>
				<input
					value={description}
					onChange={(e) => setDescription(e.target.value)}
					placeholder="Description (optional)"
					className={`${inputClass} mt-2`}
				/>
				<div className="mt-4">
					<MatchRulesEditor rules={rules} onChange={setRules} disabled={saving} />
				</div>
				{error && <p className="mt-2 text-sm text-red-500">{error}</p>}
				<div className="mt-3 flex items-center gap-2">
					<button
						type="submit"
						disabled={saving || !name.trim()}
						className="cursor-pointer rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
					>
						{saving ? 'Saving…' : 'Save'}
					</button>
					<button
						type="button"
						onClick={() => setEditing(false)}
						className="cursor-pointer rounded-md px-3 py-1.5 text-sm text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
					>
						Cancel
					</button>
				</div>
			</form>
		);
	}

	return (
		<div className="rounded-lg border border-[var(--border)] p-4 shadow-sm transition-colors hover:border-[var(--accent-border)]">
			<div className="flex items-center gap-2">
				<h3 className="truncate font-semibold text-[var(--text-h)]">{tracker.name}</h3>
				{/* Only when there's something to report. A "0" on every card would
				    be noise, and the count is exactly the thing meant to catch the
				    eye when it isn't zero. Clicking it reveals what the updates
				    actually were — the subject lines are already stored. */}
				{tracker.unread_count > 0 && (
					<button
						type="button"
						onClick={toggleUpdates}
						aria-expanded={updates !== null}
						aria-label={`${tracker.unread_count} new update${
							tracker.unread_count === 1 ? '' : 's'
						} for ${tracker.name}`}
						className="shrink-0 cursor-pointer rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs font-semibold text-white transition-opacity hover:opacity-90"
					>
						{tracker.unread_count} new
					</button>
				)}
				{/* Omitted entirely when the subject has no category — an empty
				    pill would be noise on every uncategorized card. */}
				{tracker.subject_category && (
					<span className="shrink-0 rounded-full bg-[var(--accent-bg)] px-2 py-0.5 text-xs text-[var(--text)]">
						{tracker.subject_category}
					</span>
				)}
				{tracker.url ? (
					<a
						href={tracker.url}
						target="_blank"
						rel="noreferrer"
						onClick={handleOpen}
						title={tracker.url}
						aria-label={`Open ${tracker.name}`}
						className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-[var(--accent)] focus-visible:text-[var(--accent)]"
					>
						<GlobeIcon />
					</a>
				) : (
					<button
						type="button"
						onClick={handleMarkChecked}
						title="Mark as checked — there's no link on this tracker"
						aria-label={`Mark ${tracker.name} as checked`}
						className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-[var(--accent)] focus-visible:text-[var(--accent)]"
					>
						<CheckIcon />
					</button>
				)}
				{/* Rules are only visible while editing, so the count is the only
				    sign a card is watching mail at all — and "0 rules" on a tracker
				    with no URL is the shape of one that can never do anything. */}
				{tracker.rules.length > 0 && (
					<span
						title={tracker.rules
							.map((r) => `${r.field} ${r.operator.replace('_', ' ')} “${r.value}”`)
							.join('\n')}
						className="ml-auto shrink-0 text-xs text-[var(--text)]"
					>
						{tracker.rules.length === 1 ? '1 rule' : `${tracker.rules.length} rules`}
					</span>
				)}
				<span
					className={`shrink-0 text-xs text-[var(--text)] ${
						tracker.rules.length > 0 ? '' : 'ml-auto'
					}`}
				>
					{timeAgo(tracker.last_checked)}
				</span>
				{undo && (
					<button
						type="button"
						onClick={handleUndo}
						aria-label={`Undo the last-checked update for ${tracker.name}`}
						title="Put the previous “last checked” time back"
						className="shrink-0 cursor-pointer rounded-md px-1 py-0.5 text-xs font-medium text-[var(--accent)] underline-offset-2 transition-colors hover:underline focus-visible:underline"
					>
						Undo
					</button>
				)}
				<button
					type="button"
					onClick={startEditing}
					aria-label={`Edit ${tracker.name}`}
					className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-[var(--accent)] focus-visible:text-[var(--accent)]"
				>
					<PencilIcon />
				</button>
				<button
					type="button"
					onClick={handleDelete}
					aria-label={`Delete ${tracker.name}`}
					className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-red-500 focus-visible:text-red-500"
				>
					<CloseIcon />
				</button>
			</div>
			{updates !== null && (
				<ul className="mt-3 flex flex-col gap-1 border-t border-[var(--border)] pt-3">
					{updates.map((update) => (
						<li key={update.id} className="flex items-baseline gap-2 text-sm">
							<span className="truncate text-[var(--text-h)]">
								{update.summary || '(no subject)'}
							</span>
							<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
								{timeAgo(update.detected_at)}
							</span>
						</li>
					))}
					{updates.length === 0 && (
						<li className="text-sm text-[var(--text)]">Nothing recorded yet.</li>
					)}
				</ul>
			)}
			{error && <p className="mt-2 text-sm text-red-500">{error}</p>}
		</div>
	);
}

function PencilIcon() {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			aria-hidden="true"
		>
			<path d="M12 20h9" />
			<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
		</svg>
	);
}

function CloseIcon() {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			aria-hidden="true"
		>
			<path d="M18 6L6 18M6 6l12 12" />
		</svg>
	);
}

function CheckIcon() {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			aria-hidden="true"
		>
			<path d="M20 6L9 17l-5-5" />
		</svg>
	);
}

function GlobeIcon() {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			aria-hidden="true"
		>
			<circle cx="12" cy="12" r="10" />
			<path d="M2 12h20M12 2a15 15 0 0 1 0 20a15 15 0 0 1 0-20" />
		</svg>
	);
}
