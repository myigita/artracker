import { useId, useState } from 'react';
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
	const hintId = useId();

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
			<div className="flex items-center gap-1.5">
				<h3 className="text-sm font-medium text-[var(--text-h)]">Handles</h3>

				{/* A named group so it can't be triggered by the pills' own `group`. */}
				<span className="group/hint relative inline-flex">
					<button
						type="button"
						aria-label="What are handles?"
						aria-describedby={hintId}
						className="flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-[var(--border)] text-[10px] leading-none text-[var(--text)] transition-colors hover:border-[var(--accent-border)] hover:text-[var(--text-h)] focus-visible:border-[var(--accent-border)] focus-visible:text-[var(--text-h)]"
					>
						?
					</button>
					<span
						id={hintId}
						role="tooltip"
						// focus-within as well as hover, so a keyboard can reach it.
						// pointer-events-none stops the tooltip from eating hovers meant
						// for whatever sits underneath it.
						className="pointer-events-none absolute left-0 top-full z-20 mt-1.5 w-64 rounded-md border border-[var(--border)] bg-[var(--bg)] p-2 text-xs leading-snug text-[var(--text)] opacity-0 shadow-[var(--shadow)] transition-opacity group-hover/hint:opacity-100 group-focus-within/hint:opacity-100 motion-reduce:transition-none"
					>
						What this subject is called on the platforms it posts to. Matched
						against the sender of notification mail.
					</span>
				</span>
			</div>

			<div className="mt-3 flex flex-wrap items-center gap-2">
				{subject.handles.map((handle) => (
					// The right padding permanently reserves room for the ×, so the pill
					// never changes width and hovering one can't shove the pills after it
					// sideways. Measured before this: at px-3 the × overlapped the label
					// by 9.8px, and still by 3.8px after the old 6px nudge — there was
					// simply no room for both.
					<span
						key={handle}
						className="group relative inline-flex items-center rounded-full border border-[var(--border)] py-1 pl-3 pr-7 text-xs text-[var(--text-h)]"
					>
						{/* At rest the reserved space would leave the handle looking
						    off-centre, so it's nudged right by half of it. On hover the nudge
						    goes away, which reads as the text sliding left to make room. */}
						<span className="translate-x-0 transition-transform motion-reduce:transition-none [@media(hover:hover)]:translate-x-2 [@media(hover:hover)]:group-focus-within:translate-x-0 [@media(hover:hover)]:group-hover:translate-x-0">
							{handle}
						</span>
						<button
							type="button"
							onClick={() => handleRemove(handle)}
							disabled={saving}
							aria-label={`Remove handle ${handle}`}
							// Visible by default and hidden only where hover exists: a touch
							// screen has no hover state to enter, so the reverse would leave
							// the handle permanently unremovable on a phone. Keyboards don't
							// hover either, hence group-focus-within.
							// top-1/2 with the -translate-y-1/2 correction rather than relying
							// on the flex parent's align-items, which only positions abspos
							// children by their static position and is easy to disturb.
							className="absolute right-1.5 top-1/2 -translate-y-1/2 cursor-pointer rounded-full p-0.5 text-[var(--text)] transition-opacity hover:text-red-500 focus-visible:text-red-500 disabled:cursor-not-allowed motion-reduce:transition-none [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
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
							placeholder="handle"
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
