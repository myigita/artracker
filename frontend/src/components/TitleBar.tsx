type Props<T extends string> = {
	title: string;
	tabs: { id: T; label: string }[];
	active: T;
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
		<header className="z-10 border-b border-[var(--border)] bg-[var(--bg)] md:sticky md:top-0">
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
