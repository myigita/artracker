import type { ReactNode } from 'react';

type Props = {
	open: boolean;
	id?: string;
	children: ReactNode;
};

export default function Collapse({ open, id, children }: Props) {
	return (
		<div
			id={id}
			aria-hidden={!open}
			inert={!open}
			className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none ${open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
		>
			<div className="min-h-0 overflow-hidden">{children}</div>
		</div>
	);
}

export function Chevron({ open }: { open: boolean }) {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
			aria-hidden="true"
			className={`shrink-0 transition-transform duration-200 motion-reduce:transition-none ${open ? 'rotate-180' : ''}`}
		>
			<path d="M6 9l6 6 6-6" />
		</svg>
	);
}
