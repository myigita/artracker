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
	const barRef = useRef<HTMLDivElement>(null);
	const logoRef = useRef<HTMLSpanElement>(null);
	const measureRef = useRef<HTMLDivElement>(null);
	const actionMeasureRef = useRef<HTMLDivElement>(null);
	const menuRef = useRef<HTMLDivElement>(null);
	const triggerRef = useRef<HTMLButtonElement>(null);
	// Kept after the action disappears, so its cell holds its place on tabs without one.
	const [actionWidth, setActionWidth] = useState(0);
	const [asMenu, setAsMenu] = useState(false);
	const [menuOpen, setMenuOpen] = useState(false);
	const hasAction = Boolean(action);

	// Invisible copies of the tab row and the action are measured at their natural
	// width, so the result doesn't depend on which layout is currently showing.
	useLayoutEffect(() => {
		const bar = barRef.current;
		const logo = logoRef.current;
		const measure = measureRef.current;
		if (!bar || !logo || !measure) return;
		const check = () => {
			const width = Math.max(actionWidth, actionMeasureRef.current?.offsetWidth ?? 0);
			setActionWidth(width);
			setAsMenu(measure.scrollWidth > bar.clientWidth - logo.offsetWidth - width);
		};
		const observer = new ResizeObserver(check);
		for (const el of [bar, logo, measure, actionMeasureRef.current]) if (el) observer.observe(el);
		check();
		return () => observer.disconnect();
	}, [hasAction, actionWidth]);

	useEffect(() => {
		if (!asMenu) setMenuOpen(false);
	}, [asMenu]);

	useEffect(() => {
		if (!menuOpen) return;
		const onPointer = (event: PointerEvent) => {
			if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
		};
		const onKey = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				setMenuOpen(false);
				triggerRef.current?.focus();
			}
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
				{counts[id] !== null && <span className="ml-1 text-xs font-normal">({counts[id]})</span>}
			</>
		);
	}

	function tabClass(id: T) {
		return `flex cursor-pointer items-center whitespace-nowrap px-2.5 py-2.5 text-lg font-bold uppercase transition-colors sm:px-3 ${
			active === id
				? 'bg-[var(--accent-bg)] text-[var(--text-h)]'
				: 'text-[var(--text)] hover:text-[var(--text-h)]'
		}`;
	}

	const sectionsClass = 'divide-x-[3px] divide-[var(--frame)]';

	const activeTab = tabs.find((tab) => tab.id === active);

	return (
		<header className="z-10 bg-[var(--bg)] px-4 pt-4 sm:px-6 sm:pt-6 md:sticky md:top-0">
			<div
				ref={barRef}
				className="mx-auto flex max-w-7xl flex-wrap items-stretch border-[3px] border-[var(--frame)]"
			>
				<span
					ref={logoRef}
					className="flex shrink-0 items-center border-r-[3px] border-[var(--frame)] px-3 py-2.5 text-lg font-bold uppercase tracking-tight text-[var(--text-h)] sm:px-4"
				>
					<span className="sr-only">{title}</span>
					<span aria-hidden="true">
						{[...title.slice(0, 5)].map((letter, i) => (
							<span key={i} style={{ color: `var(--logo-${i + 1})` }}>
								{letter}
							</span>
						))}
						{title.slice(5)}
					</span>
				</span>

				<div className="relative flex min-w-0 flex-1">
					<div
						aria-hidden="true"
						inert
						className="pointer-events-none invisible absolute inset-x-0 top-0 h-0 overflow-hidden"
					>
						<div ref={measureRef} className={`flex w-max ${sectionsClass}`}>
							{tabs.map(({ id, label }) => (
								<span key={id} className={tabClass(id)}>
									{tabContent(id, label)}
								</span>
							))}
						</div>
						{action && (
							<div ref={actionMeasureRef} className="flex w-max border-l-[3px]">
								{action}
							</div>
						)}
					</div>

					{asMenu ? (
						<div ref={menuRef} className="relative flex min-w-0 flex-1">
							<button
								ref={triggerRef}
								type="button"
								onClick={() => setMenuOpen((open) => !open)}
								aria-expanded={menuOpen}
								aria-controls="tab-menu"
								aria-label={`Section: ${activeTab?.label ?? ''}`}
								className={`${tabClass(active)} min-w-0 flex-1 justify-between gap-1`}
							>
								<span className="truncate">
									{activeTab && tabContent(activeTab.id, activeTab.label)}
								</span>
								<Chevron open={menuOpen} />
							</button>
							{menuOpen && (
								<div
									id="tab-menu"
									role="tablist"
									aria-orientation="vertical"
									className="absolute -inset-x-[3px] top-full z-20 mt-[3px] flex flex-col divide-y-[3px] divide-[var(--frame)] border-[3px] border-[var(--frame)] bg-[var(--bg)]"
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
												triggerRef.current?.focus();
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
						<nav className={`flex flex-1 ${sectionsClass}`} role="tablist">
							{tabs.map(({ id, label }) => (
								<button
									key={id}
									type="button"
									role="tab"
									aria-selected={active === id}
									onClick={() => onSelect(id)}
									className={`${tabClass(id)} flex-1 justify-center`}
								>
									{tabContent(id, label)}
								</button>
							))}
						</nav>
					)}
				</div>

				{asMenu
					? action && (
							<div className="flex basis-full border-t-[3px] border-[var(--frame)] *:flex-1 *:py-2.5">
								{action}
							</div>
						)
					: actionWidth > 0 && (
							<div
								style={{ width: actionWidth }}
								className="flex shrink-0 border-l-[3px] border-[var(--frame)] *:flex-1"
							>
								{action}
							</div>
						)}
			</div>
		</header>
	);
}
