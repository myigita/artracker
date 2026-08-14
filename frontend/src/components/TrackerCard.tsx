import type { Tracker } from '../api';

type Props = {
	tracker: Tracker;
};

export default function TrackerCard({ tracker }: Props) {
	return (
		<div className="rounded-lg border border-[var(--border)] p-4 shadow-sm transition-colors hover:border-[var(--accent-border)]">
			<h3 className="font-semibold text-[var(--text-h)]">{tracker.name}</h3>
			<p className="mt-1 truncate text-sm text-[var(--text)]">{tracker.url}</p>
			<p className="mt-3 text-xs text-[var(--text)]">
				{tracker.last_checked ? tracker.last_checked : 'never'}
			</p>
		</div>
	);
}
