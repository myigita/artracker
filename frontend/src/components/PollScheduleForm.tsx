import { useEffect, useState } from 'react';
import type { PollSchedule } from '../api';
import { errorDetail, setPollSchedule } from '../api';

type Props = {
	schedule: PollSchedule | null;
	onSaved: (schedule: PollSchedule) => void;
};

// Offered as a fixed list rather than a free number field: the useful values are
// few and well separated, and it makes the five-minute floor a thing you can't
// type your way past rather than an error you discover after saving.
const INTERVALS = [5, 10, 15, 30, 60, 180, 360, 720, 1440];

function label(minutes: number): string {
	if (minutes < 60) return `${minutes} minutes`;
	if (minutes === 60) return 'hour';
	if (minutes < 1440) return `${minutes / 60} hours`;
	return 'day';
}

export default function PollScheduleForm({ schedule, onSaved }: Props) {
	const [enabled, setEnabled] = useState(false);
	const [interval, setIntervalMinutes] = useState(15);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!schedule) return;
		setEnabled(schedule.enabled);
		setIntervalMinutes(schedule.interval_minutes);
	}, [schedule]);

	function save(
		next: { enabled: boolean; interval_minutes: number },
		previous: { enabled: boolean; interval_minutes: number },
	) {
		setSaving(true);
		setError(null);
		setPollSchedule(next)
			.then(onSaved)
			.catch((err) => {
				setEnabled(previous.enabled);
				setIntervalMinutes(previous.interval_minutes);
				setError(errorDetail(err) ?? 'Could not save the schedule.');
			})
			.finally(() => setSaving(false));
	}

	return (
		<section>
			<h2 className="font-semibold text-[var(--text-h)]">Automatic checks</h2>
			<p className="mt-1 text-sm text-[var(--text)]">
				Reads the mailbox on a timer, so updates appear without you pressing
				anything. Runs inside the app — nothing to set up on the host.
			</p>

			<div className="mt-3 flex flex-wrap items-center gap-3">
				<label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--text-h)]">
					<input
						type="checkbox"
						checked={enabled}
						disabled={saving}
						onChange={(event) => {
							// Saved immediately rather than behind a button: it's one
							// switch, and a toggle that needs confirming reads as broken.
							const next = event.target.checked;
							setEnabled(next);
							save(
								{ enabled: next, interval_minutes: interval },
								{ enabled, interval_minutes: interval },
							);
						}}
						className="size-4 cursor-pointer accent-[var(--accent)]"
					/>
					Check automatically
				</label>

				<label className="flex items-center gap-2 text-sm text-[var(--text)]">
					every
					<select
						value={interval}
						disabled={saving || !enabled}
						onChange={(event) => {
							const next = Number(event.target.value);
							setIntervalMinutes(next);
							save(
								{ enabled, interval_minutes: next },
								{ enabled, interval_minutes: interval },
							);
						}}
						aria-label="How often to check"
						className="cursor-pointer rounded-md border border-[var(--border)] bg-transparent px-2 py-1 text-sm text-[var(--text-h)] outline-none transition-colors focus:border-[var(--accent-border)] disabled:opacity-40"
					>
						{INTERVALS.map((minutes) => (
							<option key={minutes} value={minutes}>
								{label(minutes)}
							</option>
						))}
					</select>
				</label>
			</div>

			{schedule?.last_run_at && (
				<p className="mt-3 text-xs text-[var(--text)]">
					Last run {new Date(schedule.last_run_at).toLocaleString()}
					{schedule.last_result ? ` — ${schedule.last_result}` : ''}
				</p>
			)}

			{schedule?.enabled && schedule.next_run_at && (
				<p className="mt-1 text-xs text-[var(--text)]">
					{new Date(schedule.next_run_at).getTime() <= Date.now() + 60_000
						? 'Next run due now.'
						: `Next run around ${new Date(schedule.next_run_at).toLocaleTimeString()}.`}
				</p>
			)}

			{error && (
				<p className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-[var(--text-h)]">
					{error}
				</p>
			)}
		</section>
	);
}
