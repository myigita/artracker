import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Chevron } from './Collapse';

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
	const slotRef = useRef<HTMLDivElement>(null);
	const measureRef = useRef<HTMLDivElement>(null);
	const menuRef = useRef<HTMLDivElement>(null);
	const [collapsed, setCollapsed] = useState(false);
	const [menuOpen, setMenuOpen] = useState(false);

	// An invisible copy of the full tab row is measured against the space the
	// real one would get, so the switch tracks actual fit rather than a breakpoint.
	useLayoutEffect(() => {
		const slot = slotRef.current;
		const measure = measureRef.current;
		if (!slot || !measure) return;
		const check = () => setCollapsed(measure.scrollWidth > slot.clientWidth);
		const observer = new ResizeObserver(check);
		observer.observe(slot);
		observer.observe(measure);
		check();
		return () => observer.disconnect();
	}, []);

	useEffect(() => {
		if (!collapsed) setMenuOpen(false);
	}, [collapsed]);

	useEffect(() => {
		if (!menuOpen) return;
		const onPointer = (event: PointerEvent) => {
			if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
		};
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') setMenuOpen(false);
		};
		document.addEventListener('pointerdown', onPointer);
		document.addEventListener('keydown', onKey);
		return () => {
			document.removeEventListener('pointerdown', onPointer);
			document.removeEventListener('keydown', onKey);
		};
	}, [menuOpen]);

	function tabContent(id: T, label: string) {
		return (
			<>
				{label}
				{counts[id] !== null && <span className="text-xs font-normal"> ({counts[id]})</span>}
			</>
		);
	}

	function tabClass(id: T) {
		return `cursor-pointer whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors ${
			active === id
				? 'bg-[var(--accent-bg)] text-[var(--text-h)]'
				: 'text-[var(--text)] hover:text-[var(--text-h)]'
		}`;
	}

	const activeTab = tabs.find((tab) => tab.id === active);

	return (
		<header className="z-10 border-b border-[var(--border)] bg-[var(--bg)] md:sticky md:top-0">
			<div className="mx-auto flex max-w-4xl items-center gap-3 px-6 py-3">
				<span className="shrink-0 text-lg font-bold tracking-tight text-[var(--text-h)]">
					{[...title.slice(0, 5)].map((letter, i) => (
						<span key={i} style={{ color: `var(--logo-${i + 1})` }}>
							{letter}
						</span>
					))}
					{title.slice(5)}
				</span>

				<div ref={slotRef} className="relative min-w-0 flex-1">
					<div
						aria-hidden="true"
						className="pointer-events-none invisible absolute inset-x-0 top-0 h-0 overflow-hidden"
					>
						<div ref={measureRef} className="flex w-max gap-1">
							{tabs.map(({ id, label }) => (
								<span key={id} className={tabClass(id)}>
									{tabContent(id, label)}
								</span>
							))}
						</div>
					</div>

					{collapsed ? (
						<div ref={menuRef} className="relative w-fit max-w-full">
							<button
								type="button"
								onClick={() => setMenuOpen((open) => !open)}
								aria-expanded={menuOpen}
								aria-controls="tab-menu"
								aria-label={`Section: ${activeTab?.label ?? ''}`}
								className={`${tabClass(active)} flex max-w-full items-center gap-1`}
							>
								<span className="truncate">{activeTab?.label}</span>
								<Chevron open={menuOpen} />
							</button>
							{menuOpen && (
								<div
									id="tab-menu"
									role="tablist"
									aria-orientation="vertical"
									className="absolute left-0 top-full z-20 mt-1 flex min-w-40 flex-col gap-0.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-1 shadow-lg"
								>
									{tabs.map(({ id, label }) => (
										<button
											key={id}
											type="button"
											role="tab"
											aria-selected={active === id}
											onClick={() => {
												onSelect(id);
												setMenuOpen(false);
											}}
											className={`${tabClass(id)} text-left`}
										>
											{tabContent(id, label)}
										</button>
									))}
								</div>
							)}
						</div>
					) : (
						<nav className="flex gap-1" role="tablist">
							{tabs.map(({ id, label }) => (
								<button
									key={id}
									type="button"
									role="tab"
									aria-selected={active === id}
									onClick={() => onSelect(id)}
									className={tabClass(id)}
								>
									{tabContent(id, label)}
								</button>
							))}
						</nav>
					)}
				</div>

				{action && <div className="shrink-0">{action}</div>}
			</div>
		</header>
	);
}
