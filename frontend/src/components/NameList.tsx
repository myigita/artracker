import { useState } from 'react';
import { isConflict } from '../api';

type NameItem = {
	id: number;
	name: string;
};

type Props<T extends NameItem> = {
	label: string;
	items: T[];
	usageCount: (name: string) => number;
	usageLabel?: string;
	// Only needed when label + "s" is wrong — "categorys".
	plural?: string;
	blockedHint?: string;
	isProtected?: (item: T) => boolean;
	protectedHint?: string;
	renderExtra?: (item: T) => React.ReactNode;
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
			<p className="border-[3px] border-dashed border-[var(--frame)] p-8 text-center text-sm text-[var(--text)]">
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
								className="border-[3px] border-[var(--frame)]"
							>
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
