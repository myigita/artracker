import { useState } from 'react';
import type { Subject } from '../api';
import { errorDetail, updateSubject } from '../api';

type Props = {
	subject: Subject;
	onChanged: () => void;
};

// One comma-separated field rather than a chip-input widget. Handles are short,
// there are rarely more than two or three, and they're edited about once per
// subject ever — a full tag editor would be far more machinery than that earns.
//
// The backend lowercases and de-duplicates, so this deliberately doesn't: doing
// it here too would just be a second implementation to keep in sync.
export default function SubjectHandles({ subject, onChanged }: Props) {
	const [editing, setEditing] = useState(false);
	const [value, setValue] = useState('');
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function startEditing() {
		setValue(subject.handles.join(', '));
		setError(null);
		setEditing(true);
	}

	function handleSubmit(event: React.FormEvent) {
		event.preventDefault();

		const handles = value
			.split(',')
			.map((handle) => handle.trim())
			.filter(Boolean);

		setSaving(true);
		setError(null);
		updateSubject(subject.id, { handles })
			.then(() => {
				setEditing(false);
				onChanged();
			})
			// The 409 detail names the handle and who already owns it, which is far
			// more use than a generic failure message.
			.catch((err) => setError(errorDetail(err) ?? 'Could not save the handles.'))
			.finally(() => setSaving(false));
	}

	if (editing) {
		return (
			// The Save button exists because nothing otherwise told you how to save.
			// The first version relied on implicit submission alone, so the only
			// affordance was a tooltip saying "Enter to save" — invisible until you
			// hover something you have no reason to hover. A visible control also
			// gives the disabled/"Saving…" state somewhere to live.
			<form onSubmit={handleSubmit} className="flex shrink-0 flex-col gap-1">
				<div className="flex items-center gap-1">
					<input
						autoFocus
						value={value}
						disabled={saving}
						onChange={(event) => setValue(event.target.value)}
						// Escape cancels. Blur deliberately does nothing — discarding a
						// half-typed handle because focus moved would be worse than an
						// input that stays open.
						onKeyDown={(event) => {
							if (event.key === 'Escape') setEditing(false);
						}}
						placeholder="peargor, pear_art"
						aria-label={`Handles for ${subject.name}`}
						title="Comma-separated"
						className={`w-32 rounded-md border bg-transparent px-2 py-1 text-xs outline-none transition-colors disabled:opacity-40 sm:w-44 ${
							error
								? 'border-red-500 text-red-500'
								: 'border-[var(--border)] text-[var(--text-h)] focus:border-[var(--accent-border)]'
						}`}
					/>
					<button
						type="submit"
						disabled={saving}
						className="cursor-pointer rounded-md bg-[var(--accent)] px-2 py-1 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
					>
						{saving ? 'Saving…' : 'Save'}
					</button>
					<button
						type="button"
						onClick={() => setEditing(false)}
						className="cursor-pointer rounded-md px-1 py-1 text-xs text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
					>
						Cancel
					</button>
				</div>
				{/* The 409 names the clashing handle and its current owner, which is
				    too useful to hide in a tooltip. */}
				{error && <p className="max-w-64 text-xs text-red-500">{error}</p>}
			</form>
		);
	}

	return (
		<button
			type="button"
			onClick={startEditing}
			aria-label={`Edit handles for ${subject.name}`}
			title={
				subject.handles.length
					? `Matched against notification mail from ${subject.handles.join(', ')}`
					: 'Add a handle to match this subject against notification mail'
			}
			className="shrink-0 cursor-pointer truncate rounded-md border border-dashed border-[var(--border)] px-2 py-1 text-xs text-[var(--text)] transition-colors hover:border-[var(--accent-border)] hover:text-[var(--text-h)]"
		>
			{subject.handles.length ? subject.handles.join(', ') : '+ handle'}
		</button>
	);
}
