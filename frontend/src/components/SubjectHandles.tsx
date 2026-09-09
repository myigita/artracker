import { useState } from 'react';
import type { Subject } from '../api';
import { errorDetail, updateSubject } from '../api';

type Props = {
	subject: Subject;
	onChanged: () => void;
};

// Every edit sends the whole list, because that's the shape of the API — PATCH
// replaces handles wholesale rather than adding or removing one. Add and remove
// are just two ways of computing the next list.
export default function SubjectHandles({ subject, onChanged }: Props) {
	const [adding, setAdding] = useState(false);
	const [value, setValue] = useState('');
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function save(handles: string[], onSuccess?: () => void) {
		setSaving(true);
		setError(null);
		updateSubject(subject.id, { handles })
			.then(() => {
				onSuccess?.();
				onChanged();
			})
			// The 409 names the clashing handle and the subject that already owns
			// it, which is far more use than a generic failure message.
			.catch((err) => setError(errorDetail(err) ?? 'Could not save the handles.'))
			.finally(() => setSaving(false));
	}

	function handleAdd(event: React.FormEvent) {
		event.preventDefault();
		const next = value.trim();
		if (!next) return;

		// Lowercasing and de-duplicating is the backend's job; doing it here too
		// would be a second implementation to keep in step with it.
		save([...subject.handles, next], () => {
			setValue('');
			setAdding(false);
		});
	}

	function handleRemove(handle: string) {
		save(subject.handles.filter((existing) => existing !== handle));
	}

	return (
		<div>
			<h3 className="text-sm font-medium text-[var(--text-h)]">Handles</h3>
			<p className="mt-0.5 text-xs text-[var(--text)]">
				What this subject is called on the platforms it posts to. Matched against
				the sender of notification mail — <code>peargor</code> catches mail from{' '}
				<code>peargor@creator.patreon.com</code>.
			</p>

			<div className="mt-3 flex flex-wrap items-center gap-2">
				{subject.handles.map((handle) => (
					<span
						key={handle}
						className="group flex items-center gap-1 rounded-full border border-[var(--border)] py-1 pl-2.5 pr-1.5 text-xs text-[var(--text-h)]"
					>
						{handle}
						<button
							type="button"
							onClick={() => handleRemove(handle)}
							disabled={saving}
							aria-label={`Remove handle ${handle}`}
							// Hidden until hover, as asked — but ONLY where hovering exists.
							// On a touch screen there is no hover state to enter, so outside
							// that media query the button stays visible; otherwise a handle
							// could never be removed on a phone.
							//
							// group-focus-within, not focus-visible, because keyboards don't
							// hover either and the × has to appear when focus reaches it.
							className="cursor-pointer rounded-full p-0.5 text-[var(--text)] transition-opacity hover:text-red-500 focus-visible:text-red-500 disabled:cursor-not-allowed [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
						>
							<svg
								width="12"
								height="12"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								strokeWidth="3"
								aria-hidden="true"
							>
								<path d="M18 6L6 18M6 6l12 12" />
							</svg>
						</button>
					</span>
				))}

				{adding ? (
					<form onSubmit={handleAdd} className="flex items-center gap-1">
						<input
							autoFocus
							value={value}
							disabled={saving}
							onChange={(event) => setValue(event.target.value)}
							onKeyDown={(event) => {
								if (event.key === 'Escape') {
									setValue('');
									setAdding(false);
								}
							}}
							placeholder="peargor"
							aria-label={`New handle for ${subject.name}`}
							className="w-32 rounded-full border border-[var(--border)] bg-transparent px-2.5 py-1 text-xs text-[var(--text-h)] outline-none transition-colors focus:border-[var(--accent-border)] disabled:opacity-40 sm:w-40"
						/>
						<button
							type="submit"
							disabled={saving || !value.trim()}
							className="cursor-pointer rounded-full bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
						>
							{saving ? 'Saving…' : 'Add'}
						</button>
						<button
							type="button"
							onClick={() => {
								setValue('');
								setAdding(false);
								setError(null);
							}}
							className="cursor-pointer rounded-full px-2 py-1 text-xs text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
						>
							Cancel
						</button>
					</form>
				) : (
					<button
						type="button"
						onClick={() => {
							setError(null);
							setAdding(true);
						}}
						className="cursor-pointer rounded-full border border-dashed border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text)] transition-colors hover:border-[var(--accent-border)] hover:text-[var(--text-h)]"
					>
						+ Add handle
					</button>
				)}
			</div>

			{subject.handles.length === 0 && !adding && (
				<p className="mt-2 text-xs text-[var(--text)]">
					No handles yet, so no notification mail will ever match this subject.
				</p>
			)}

			{error && <p className="mt-2 text-xs text-red-500">{error}</p>}
		</div>
	);
}
