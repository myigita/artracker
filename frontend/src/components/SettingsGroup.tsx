import { useId, type ReactNode } from 'react';

type Props = {
	title: string;
	description?: string;
	children: ReactNode;
};

export default function SettingsGroup({ title, description, children }: Props) {
	const headingId = useId();

	return (
		<section aria-labelledby={headingId} className="rounded-lg border border-[var(--border)]">
			<header className="border-b border-[var(--border)] px-5 py-3">
				<h2 id={headingId} className="font-semibold text-[var(--text-h)]">
					{title}
				</h2>
				{description && <p className="mt-0.5 text-sm text-[var(--text)]">{description}</p>}
			</header>
			<div className="flex flex-col divide-y divide-[var(--border)] px-5 [&>*]:py-5">
				{children}
			</div>
		</section>
	);
}
