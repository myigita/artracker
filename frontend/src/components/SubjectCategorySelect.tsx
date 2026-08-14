import { useState } from 'react';
import type { Category, Subject } from '../api';
import { updateSubject } from '../api';

type Props = {
	subject: Subject;
	categories: Category[];
	onChanged: () => void;
};

// A <select> can't hold null, so "no category" is the empty string in the DOM
// and gets translated back to an explicit null for the PATCH — which is what
// the API reads as "clear it".
const NONE = '';

export default function SubjectCategorySelect({ subject, categories, onChanged }: Props) {
	const [saving, setSaving] = useState(false);
	const [failed, setFailed] = useState(false);

	function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
		const choice = event.target.value;

		setSaving(true);
		setFailed(false);

		updateSubject(subject.id, { category_name: choice === NONE ? null : choice })
			.then(() => onChanged())
			.catch(() => setFailed(true))
			.finally(() => setSaving(false));
	}

	// With no categories defined the only option is "No category", so the control
	// would be a dead end. Disabled with an explanation beats silently useless.
	const noCategoriesYet = categories.length === 0;

	return (
		<select
			value={subject.category_name ?? NONE}
			onChange={handleChange}
			disabled={saving || noCategoriesYet}
			aria-label={`Category for ${subject.name}`}
			title={
				failed
					? 'Could not save — try again'
					: noCategoriesYet
						? 'Add a category first'
						: undefined
			}
			className={`w-28 shrink-0 truncate rounded-md border bg-transparent px-2 py-1 text-xs outline-none transition-colors focus:border-[var(--accent-border)] disabled:opacity-40 sm:w-36 ${
				failed
					? 'border-red-500 text-red-500'
					: 'border-[var(--border)] text-[var(--text)]'
			}`}
		>
			<option value={NONE}>No category</option>
			{categories.map((category) => (
				<option key={category.id} value={category.name}>
					{category.name}
				</option>
			))}
		</select>
	);
}
