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
	'w-full border-[3px] border-[var(--frame)] bg-transparent px-3 py-2 text-sm ' +
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
	const [rules, setRules] = useState<MatchRuleIn[]>(() =>
		tracker.rules.map(({ field, operator, value }) => ({ field, operator, value })),
	);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	// Boxed, because null ("never checked") is a valid value to restore.
	const [undo, setUndo] = useState<{ previous: string | null } | null>(null);
	const [updates, setUpdates] = useState<Update[] | null>(null);

	// No timer on purpose: the user notices the mistake after coming back from the other tab.

	function handleOpen() {
		// Read this BEFORE the check lands — afterwards it's already overwritten.
		const previous = tracker.last_checked;

		// Fire-and-forget: a failed stamp must not block the link.
		checkTracker(tracker.id)
			.then(() => {
				setUndo({ previous });
				onChecked();
			})
			.catch(() => {});
	}

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
		if (!window.confirm(`Delete “${tracker.name}” and its recorded updates? This cannot be undone.`)) return;
		setError(null);
		deleteTracker(tracker.id)
			.then(() => onDeleted())
			.catch(() => setError('Could not delete this tracker.'));
	}

	function startEditing() {
		setName(tracker.name);
		setUrl(tracker.url);
		setDescription(tracker.description ?? '');
		setRules(tracker.rules.map(({ field, operator, value }) => ({ field, operator, value })));
		setError(null);
		setEditing(true);
	}

	function toggleEditing() {
		if (saving) return;
		if (editing) setEditing(false);
		else startEditing();
	}

	function handleCardClick(event: React.MouseEvent<HTMLDivElement>) {
		const target = event.target;
		if (!(target instanceof Element)) return;
		// Nested actions and the expanded form handle their own clicks.
		if (target.closest('button, a, input, select, textarea, label, form')) return;
		if (window.getSelection()?.toString()) return;
		toggleEditing();
	}

	function handleSave(event: React.FormEvent) {
		event.preventDefault();
		if (!name.trim()) return;

		setSaving(true);
		setError(null);
		updateTracker(tracker.id, {
			name: name.trim(),
			url: url.trim(),
			description: description.trim() || null,
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


	return (
		<div onClick={handleCardClick} className="group/card cursor-pointer border-[3px] border-[var(--frame)] p-4 transition-colors hover:border-[var(--accent)]">
			<div className="flex flex-wrap items-center gap-x-2 gap-y-1">
				<h3 className="min-w-0 basis-full break-words font-semibold text-[var(--text-h)] sm:basis-auto">
					{tracker.name}
				</h3>
				<div className="flex items-center gap-2">
				{tracker.unread_count > 0 && (
					<button
						type="button"
						onClick={toggleUpdates}
						aria-expanded={updates !== null}
						aria-label={`${tracker.unread_count} new update${
							tracker.unread_count === 1 ? '' : 's'
						} for ${tracker.name}`}
						className="shrink-0 cursor-pointer rounded-full bg-[var(--accent)] px-2 py-0.5 text-xs font-semibold text-[var(--on-accent)] transition-opacity hover:opacity-90"
					>
						{tracker.unread_count} new
					</button>
				)}
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
						className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-green-500 focus-visible:text-green-500"
					>
						<CheckIcon />
					</button>
				)}
				</div>
				<div className="ml-auto flex shrink-0 items-center gap-2">
				{tracker.rules.length > 0 && (
					<span
						title={tracker.rules
							.map((r) => `${r.field} ${r.operator.replace('_', ' ')} “${r.value}”`)
							.join('\n')}
						className="shrink-0 text-xs text-[var(--text)]"
					>
						{tracker.rules.length === 1 ? '1 rule' : `${tracker.rules.length} rules`}
					</span>
				)}
				<span className="shrink-0 text-xs text-[var(--text)]">
					{timeAgo(tracker.last_checked)}
				</span>
				{undo && (
					<button
						type="button"
						onClick={handleUndo}
						aria-label={`Undo the last-checked update for ${tracker.name}`}
						title="Put the previous “last checked” time back"
						className="shrink-0 cursor-pointer px-1 py-0.5 text-xs font-medium text-[var(--accent)] underline-offset-2 transition-colors hover:underline focus-visible:underline"
					>
						Undo
					</button>
				)}
				<button
					type="button"
					onClick={handleDelete}
					aria-label={`Delete ${tracker.name}`}
					className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-[color,opacity] hover:text-red-500 focus-visible:text-red-500 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover/card:opacity-100 [@media(hover:hover)]:group-focus-within/card:opacity-100 motion-reduce:transition-none"
				>
					<CloseIcon />
				</button>
				<button
					type="button"
					onClick={toggleEditing}
					disabled={saving}
					aria-expanded={editing}
					aria-controls={`tracker-editor-${tracker.id}`}
					aria-label={`${editing ? 'Collapse' : 'Expand'} ${tracker.name}`}
					className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-[var(--accent)] focus-visible:text-[var(--accent)]"
				>
					<span className={`flex transition-transform duration-200 motion-reduce:transition-none ${editing ? 'rotate-180' : ''}`}><ChevronIcon /></span>
				</button>
				</div>
			</div>
			<div
				id={`tracker-editor-${tracker.id}`}
				aria-hidden={!editing}
				inert={!editing}
				className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none ${editing ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
			>
				<div className="min-h-0 overflow-hidden">
			<form
				onSubmit={handleSave}
				className="mt-4 cursor-auto border-t border-[var(--border)] pt-4"
			>
				<input
					value={name}
					onChange={(e) => setName(e.target.value)}
					placeholder="Name"
					aria-label="Name"
					className={inputClass}
				/>
				<input
					value={url}
					onChange={(e) => setUrl(e.target.value)}
					placeholder="URL"
					aria-label="URL"
					className={`${inputClass} mt-2`}
				/>
				<input
					value={description}
					onChange={(e) => setDescription(e.target.value)}
					placeholder="Description (optional)"
					aria-label="Description (optional)"
					className={`${inputClass} mt-2`}
				/>
				<div className="mt-4">
					<MatchRulesEditor rules={rules} onChange={setRules} disabled={saving} />
				</div>
				<div className="mt-3 flex items-center gap-2">
					<button
						type="submit"
						disabled={saving || !name.trim()}
						className="cursor-pointer border-[3px] border-[var(--frame)] bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-[var(--on-accent)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
					>
						{saving ? 'Saving…' : 'Save'}
					</button>
					<button
						type="button"
						onClick={() => setEditing(false)}
						className="cursor-pointer border-[3px] border-[var(--frame)] px-3 py-1.5 text-sm text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
					>
						Cancel
					</button>
				</div>
			</form>
				</div>
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

function ChevronIcon() {
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
			<path d="m6 9 6 6 6-6" />
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
