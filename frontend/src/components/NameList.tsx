import { useState } from 'react';
import { isConflict } from '../api';

// Subjects and Platforms have identical shape, so one component serves both.
type NameItem = {
	id: number;
	name: string;
};

type Props = {
	label: string;
	items: NameItem[];
	// How many trackers point at this name. Computed by the parent from the
	// tracker list it already has — no extra endpoint needed.
	usageCount: (name: string) => number;
	onDelete: (id: number) => Promise<unknown>;
	onDeleted: () => void;
};

export default function NameList({ label, items, usageCount, onDelete, onDeleted }: Props) {
	const [error, setError] = useState<string | null>(null);
	const [busyId, setBusyId] = useState<number | null>(null);

	function handleDelete(item: NameItem) {
		setBusyId(item.id);
		setError(null);

		onDelete(item.id)
			.then(() => onDeleted())
			.catch((err) => {
				setError(
					isConflict(err)
						? `“${item.name}” still has trackers. Delete those first.`
						: `Could not delete “${item.name}”.`,
				);
			})
			.finally(() => setBusyId(null));
	}

	if (items.length === 0) {
		return (
			<p className="rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
				No {label.toLowerCase()}s yet.
			</p>
		);
	}

	return (
		<>
			{error && <p className="mb-3 text-sm text-red-500">{error}</p>}
			<div className="flex flex-col gap-2">
				{items.map((item) => {
					const count = usageCount(item.name);
					return (
						<div
							key={item.id}
							className="flex items-center gap-3 rounded-lg border border-[var(--border)] px-4 py-3"
						>
							<span className="truncate font-medium text-[var(--text-h)]">
								{item.name}
							</span>
							<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
								{count === 1 ? '1 tracker' : `${count} trackers`}
							</span>
							<button
								type="button"
								onClick={() => handleDelete(item)}
								disabled={busyId === item.id}
								aria-label={`Delete ${item.name}`}
								title={
									count > 0
										? 'Has trackers — delete those first'
										: `Delete ${item.name}`
								}
								className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-red-500 focus-visible:text-red-500 disabled:opacity-40"
							>
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
							</button>
						</div>
					);
				})}
			</div>
		</>
	);
}
