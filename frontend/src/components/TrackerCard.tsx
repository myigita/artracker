import { useState } from 'react';
import type { Tracker } from '../api';
import { checkTracker, deleteTracker, updateTracker } from '../api';

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
	const [saving, setSaving] = useState(false);

	function handleOpen() {
		checkTracker(tracker.id)
			.then(() => onChecked())
			.catch(() => {});
	}

	function handleDelete() {
		deleteTracker(tracker.id).then(() => onDeleted());
	}

	function startEditing() {
		// Reset the fields from props each time, so a cancelled edit
		// doesn't leave stale text behind on the next open.
		setName(tracker.name);
		setUrl(tracker.url);
		setDescription(tracker.description ?? '');
		setEditing(true);
	}

	function handleSave(event: React.FormEvent) {
		event.preventDefault();
		if (!name.trim() || !url.trim()) return;

		setSaving(true);
		updateTracker(tracker.id, {
			name: name.trim(),
			url: url.trim(),
			description: description.trim() || null,
		})
			.then(() => {
				setEditing(false);
				onUpdated();
			})
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
				<div className="mt-3 flex items-center gap-2">
					<button
						type="submit"
						disabled={saving || !name.trim() || !url.trim()}
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
				<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
					{timeAgo(tracker.last_checked)}
				</span>
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
