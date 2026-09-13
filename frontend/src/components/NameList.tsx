import { useState } from 'react';
import { isConflict } from '../api';

// Subjects, Platforms and Categories all reduce to an id and a name, so one
// component serves all three. Generic in T rather than fixed to NameItem so
// renderExtra can see the full item — the subjects list needs `category_name`,
// which the other two don't have.
type NameItem = {
	id: number;
	name: string;
};

type Props<T extends NameItem> = {
	label: string;
	items: T[];
	// How many rows point at this name. Computed by the parent from lists it
	// already has in state — no extra endpoint needed.
	usageCount: (name: string) => number;
	// What the count counts. Subjects and platforms are used by trackers;
	// categories are used by subjects.
	usageLabel?: string;
	// Only needed when label + "s" is wrong — "categorys".
	plural?: string;
	// What to do about it when a delete is refused.
	blockedHint?: string;
	// Rows that can never be deleted, whatever their usage count. The button is
	// disabled with an explanation rather than hidden, so its absence doesn't
	// read as a rendering bug.
	isProtected?: (item: T) => boolean;
	protectedHint?: string;
	// Optional per-row control, rendered after the name. Always visible.
	renderExtra?: (item: T) => React.ReactNode;
	// Optional detail panel, revealed by a chevron. Supplying this is what makes
	// rows expandable at all — lists without it (platforms, categories) render
	// exactly as before, with no chevron and nothing to open.
	renderExpanded?: (item: T) => React.ReactNode;
	onDelete: (id: number) => Promise<unknown>;
	onDeleted: () => void;
};

export default function NameList<T extends NameItem>({
	label,
	items,
	usageCount,
	usageLabel = 'tracker',
	plural = `${label.toLowerCase()}s`,
	blockedHint = 'Delete those first.',
	isProtected,
	protectedHint = 'Built in — can’t be deleted.',
	renderExtra,
	renderExpanded,
	onDelete,
	onDeleted,
}: Props<T>) {
	const [error, setError] = useState<string | null>(null);
	const [busyId, setBusyId] = useState<number | null>(null);
	// A set rather than a single id: opening one row shouldn't close another.
	// Comparing two subjects' handles is a real thing to want to do.
	const [expanded, setExpanded] = useState<Set<number>>(new Set());

	function toggle(id: number) {
		setExpanded((current) => {
			const next = new Set(current);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	}

	function handleDelete(item: T) {
		setBusyId(item.id);
		setError(null);

		onDelete(item.id)
			.then(() => onDeleted())
			.catch((err) => {
				setError(
					isConflict(err)
						? `“${item.name}” still has ${usageLabel}s. ${blockedHint}`
						: `Could not delete “${item.name}”.`,
				);
			})
			.finally(() => setBusyId(null));
	}

	if (items.length === 0) {
		return (
			<p className="rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
				No {plural} yet.
			</p>
		);
	}

	return (
		<>
			{error && <p className="mb-3 text-sm text-red-500">{error}</p>}
			<div className="flex flex-col gap-2">
				{items.map((item) => {
					const count = usageCount(item.name);
					const isOpen = expanded.has(item.id);
					const protectedRow = isProtected?.(item) ?? false;
					return (
							<div
								key={item.id}
								className="rounded-lg border border-[var(--border)]"
							>
								{/* flex-wrap so the header degrades by stacking rather than
								    overflowing the viewport — the subjects header carries a
								    chevron, name, category select, count and delete. */}
								<div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
									{renderExpanded && (
										<button
											type="button"
											onClick={() => toggle(item.id)}
											aria-expanded={isOpen}
											aria-label={`${isOpen ? 'Collapse' : 'Expand'} ${item.name}`}
											className="-ml-1 shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-[var(--text-h)] focus-visible:text-[var(--text-h)]"
										>
											<svg
												width="16"
												height="16"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												aria-hidden="true"
												className={`transition-transform motion-reduce:transition-none ${
													isOpen ? 'rotate-90' : ''
												}`}
											>
												<path d="M9 6l6 6-6 6" />
											</svg>
										</button>
									)}
									<span className="truncate font-medium text-[var(--text-h)]">
										{item.name}
									</span>
									{renderExtra?.(item)}
									<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
										{count === 1 ? `1 ${usageLabel}` : `${count} ${usageLabel}s`}
									</span>
									{/* The × is omitted for protected rows rather than disabled — a
								    greyed-out one still reads as something you might be able to
								    click. A label takes its slot so the row stays aligned and
								    the absence explains itself instead of looking like a bug. */}
									{protectedRow && (
										<span
											title={protectedHint}
											className="shrink-0 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text)]"
										>
											Built in
										</span>
									)}
									{!protectedRow && (
										<button
											type="button"
											onClick={() => handleDelete(item)}
											disabled={busyId === item.id}
											aria-label={`Delete ${item.name}`}
											title={
												count > 0
													? `Still has ${usageLabel}s — ${blockedHint.toLowerCase()}`
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
									)}
								</div>

								{renderExpanded && isOpen && (
									<div className="border-t border-[var(--border)] px-4 py-3">
										{renderExpanded(item)}
									</div>
								)}
							</div>
						);
				})}
			</div>
		</>
	);
}
