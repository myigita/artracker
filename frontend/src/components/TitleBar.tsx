// The app's one piece of chrome: wordmark, tab buttons, and whatever action
// belongs to the current tab. Generic in the tab id so TrackerPanel keeps
// owning the Tab union — this component never needs to know the tab names.
type Props<T extends string> = {
	title: string;
	tabs: { id: T; label: string }[];
	active: T;
	// null means "no count to show" — see counts in TrackerPanel.
	counts: Record<T, number | null>;
	onSelect: (id: T) => void;
	action?: React.ReactNode;
};

export default function TitleBar<T extends string>({
	title,
	tabs,
	active,
	counts,
	onSelect,
	action,
}: Props<T>) {
	return (
		// Sticky so the tabs stay reachable once the tracker list gets long. The
		// bar spans the full width; only its contents line up with the column
		// below, so the border reads as a real edge rather than a floating box.
		// Sticky only once the bar is a single row (measured: it stops wrapping
		// around the md breakpoint). Narrower than that it wraps to ~170px, and
		// pinning that much chrome to the top of a phone screen costs more than
		// the always-visible tabs are worth.
		<header className="z-10 border-b border-[var(--border)] bg-[var(--bg)] md:sticky md:top-0">
			{/* Wider than the max-w-2xl content column below on purpose: at the
			    column's width the wordmark, five tabs and the action button don't
			    fit on one line, and a title bar that wraps to two rows isn't a
			    title bar any more. */}
			<div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-3 gap-y-2 px-6 py-3">
				<span className="text-lg font-bold tracking-tight text-[var(--text-h)]">
					{title}
				</span>

				<nav className="flex flex-wrap gap-1" role="tablist">
					{tabs.map(({ id, label }) => (
						<button
							key={id}
							type="button"
							role="tab"
							aria-selected={active === id}
							onClick={() => onSelect(id)}
							className={`cursor-pointer rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors ${
								active === id
									? 'bg-[var(--accent-bg)] text-[var(--text-h)]'
									: 'text-[var(--text)] hover:text-[var(--text-h)]'
							}`}
						>
							{label}
							{counts[id] !== null && (
								<span className="text-xs font-normal"> ({counts[id]})</span>
							)}
						</button>
					))}
				</nav>

				{action && <div className="ml-auto">{action}</div>}
			</div>
		</header>
	);
}
