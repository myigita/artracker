import { useId, useState, type ReactNode } from 'react';
import Collapse, { Chevron } from './Collapse';

type Props = {
	title: string;
	description?: string;
	defaultOpen?: boolean;
	children: ReactNode;
};

export default function SettingsGroup({ title, description, defaultOpen = true, children }: Props) {
	const [open, setOpen] = useState(defaultOpen);
	const headingId = useId();
	const contentId = useId();

	return (
		<section aria-labelledby={headingId} className="border-[3px] border-[var(--frame)]">
			<h2>
				<button
					type="button"
					onClick={() => setOpen((value) => !value)}
					aria-expanded={open}
					aria-controls={contentId}
					className="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
				>
					<span className="flex-1">
						<span id={headingId} className="block font-semibold text-[var(--text-h)]">
							{title}
						</span>
						{description && <span className="mt-0.5 block text-sm">{description}</span>}
					</span>
					<Chevron open={open} />
				</button>
			</h2>
			<Collapse open={open} id={contentId}>
				<div className="flex flex-col divide-y divide-[var(--border)] border-t border-[var(--border)] px-5 [&>*]:py-5">
					{children}
				</div>
			</Collapse>
		</section>
	);
}
