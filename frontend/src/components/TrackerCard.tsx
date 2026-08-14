import type { Tracker } from '../api';
import { checkTracker, deleteTracker } from '../api';

type Props = {
	tracker: Tracker;
	onChecked: () => void;
	onDeleted: () => void;
};

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

export default function TrackerCard({ tracker, onChecked, onDeleted }: Props) {
	function handleOpen() {
		checkTracker(tracker.id)
			.then(() => onChecked())
			.catch(() => {});
	}

	function handleDelete() {
		deleteTracker(tracker.id).then(() => onDeleted());
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
					className="shrink-0 text-[var(--text)] transition-colors hover:text-[var(--accent)] focus-visible:text-[var(--accent)]"
				>
					<GlobeIcon />
				</a>
				<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
					{timeAgo(tracker.last_checked)}
				</span>
				<button
					type="button"
					onClick={handleDelete}
					aria-label={`Delete ${tracker.name}`}
					className="shrink-0 cursor-pointer text-[var(--text)] transition-colors hover:text-red-500 focus-visible:text-red-500"
				>
					<CloseIcon />
				</button>
			</div>
		</div>
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
