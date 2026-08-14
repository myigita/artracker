import { useState } from 'react';
import { isConflict } from '../api';

type Props = {
	label: string;
	// Passed in by the parent so this one component serves both subjects and
	// platforms — they differ only in which endpoint they hit.
	onCreate: (name: string) => Promise<unknown>;
	onCreated: (name: string) => void;
	onCancel: () => void;
};

export default function AddNameForm({ label, onCreate, onCreated, onCancel }: Props) {
	const [name, setName] = useState('');
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function handleSubmit(event: React.FormEvent) {
		event.preventDefault();
		const trimmed = name.trim();
		if (!trimmed || saving) return;

		setSaving(true);
		setError(null);

		onCreate(trimmed)
			.then(() => {
				setName('');
				onCreated(trimmed);
			})
			.catch((err) => {
				setError(
					isConflict(err)
						? `“${trimmed}” already exists.`
						: `Could not add that ${label.toLowerCase()}.`,
				);
			})
			.finally(() => setSaving(false));
	}

	return (
		<form
			onSubmit={handleSubmit}
			className="mb-4 rounded-lg border border-[var(--border)] p-4"
		>
			<label className="mb-1 block text-xs font-medium text-[var(--text)]">
				{label}
			</label>
			<input
				autoFocus
				value={name}
				onChange={(e) => setName(e.target.value)}
				placeholder={`New ${label.toLowerCase()} name`}
				className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm text-[var(--text-h)] outline-none focus:border-[var(--accent-border)]"
			/>

			{error && <p className="mt-2 text-sm text-red-500">{error}</p>}

			<div className="mt-3 flex items-center gap-2">
				<button
					type="submit"
					disabled={!name.trim() || saving}
					className="cursor-pointer rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
				>
					{saving ? 'Adding…' : `Add ${label.toLowerCase()}`}
				</button>
				<button
					type="button"
					onClick={onCancel}
					className="cursor-pointer rounded-md px-3 py-1.5 text-sm text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
				>
					Cancel
				</button>
			</div>
		</form>
	);
}
