import { useState, useEffect } from 'react';
import type { Subject, Platform } from '../api';
import {
	getSubjects,
	getPlatforms,
	ensureSubject,
	ensurePlatform,
	createTracker,
} from '../api';

type Props = {
	onAdded: () => void;
	onCancel: () => void;
};

// Sentinel for the "new…" dropdown option. A real name could never collide
// with this, and it keeps the choice in one piece of state instead of two.
const NEW = '__new__';

const inputClass =
	'w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm ' +
	'text-[var(--text-h)] outline-none focus:border-[var(--accent-border)]';

const labelClass = 'mb-1 block text-xs font-medium text-[var(--text)]';

export default function AddTrackerForm({ onAdded, onCancel }: Props) {
	const [subjects, setSubjects] = useState<Subject[]>([]);
	const [platforms, setPlatforms] = useState<Platform[]>([]);

	const [subjectChoice, setSubjectChoice] = useState('');
	const [newSubject, setNewSubject] = useState('');
	const [platformChoice, setPlatformChoice] = useState('');
	const [newPlatform, setNewPlatform] = useState('');

	const [url, setUrl] = useState('');
	const [name, setName] = useState('');
	const [description, setDescription] = useState('');

	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		getSubjects().then(setSubjects).catch(() => {});
		getPlatforms().then(setPlatforms).catch(() => {});
	}, []);

	// The name we'll actually send, whichever way it was chosen.
	const subjectName = subjectChoice === NEW ? newSubject.trim() : subjectChoice;
	const platformName = platformChoice === NEW ? newPlatform.trim() : platformChoice;
	const canSubmit = Boolean(subjectName && platformName && url.trim()) && !saving;

	async function handleSubmit(event: React.FormEvent) {
		// Without this the browser does a full page reload and the SPA dies.
		event.preventDefault();
		if (!canSubmit) return;

		setSaving(true);
		setError(null);

		try {
			// The tracker POST 400s on unknown names, so make sure both exist first.
			if (subjectChoice === NEW) await ensureSubject(subjectName);
			if (platformChoice === NEW) await ensurePlatform(platformName);

			await createTracker({
				subject_name: subjectName,
				platform_name: platformName,
				url: url.trim(),
				...(name.trim() && { name: name.trim() }),
				...(description.trim() && { description: description.trim() }),
			});

			onAdded();
		} catch {
			setError('Could not add the tracker. Check the values and try again.');
		} finally {
			setSaving(false);
		}
	}

	return (
		<form
			onSubmit={handleSubmit}
			className="mb-4 rounded-lg border border-[var(--border)] p-4"
		>
			<div className="flex flex-col gap-3 sm:flex-row">
				<div className="flex-1">
					<label className={labelClass} htmlFor="subject">Subject</label>
					<select
						id="subject"
						value={subjectChoice}
						onChange={(e) => setSubjectChoice(e.target.value)}
						className={inputClass}
					>
						<option value="">Select…</option>
						{subjects.map((s) => (
							<option key={s.id} value={s.name}>{s.name}</option>
						))}
						<option value={NEW}>+ new…</option>
					</select>
					{subjectChoice === NEW && (
						<input
							autoFocus
							value={newSubject}
							onChange={(e) => setNewSubject(e.target.value)}
							placeholder="New subject name"
							className={`${inputClass} mt-2`}
						/>
					)}
				</div>

				<div className="flex-1">
					<label className={labelClass} htmlFor="platform">Platform</label>
					<select
						id="platform"
						value={platformChoice}
						onChange={(e) => setPlatformChoice(e.target.value)}
						className={inputClass}
					>
						<option value="">Select…</option>
						{platforms.map((p) => (
							<option key={p.id} value={p.name}>{p.name}</option>
						))}
						<option value={NEW}>+ new…</option>
					</select>
					{platformChoice === NEW && (
						<input
							value={newPlatform}
							onChange={(e) => setNewPlatform(e.target.value)}
							placeholder="New platform name"
							className={`${inputClass} mt-2`}
						/>
					)}
				</div>
			</div>

			<div className="mt-3">
				<label className={labelClass} htmlFor="url">URL</label>
				<input
					id="url"
					value={url}
					onChange={(e) => setUrl(e.target.value)}
					placeholder="https://…"
					className={inputClass}
				/>
			</div>

			<div className="mt-3 flex flex-col gap-3 sm:flex-row">
				<div className="flex-1">
					<label className={labelClass} htmlFor="name">Name (optional)</label>
					<input
						id="name"
						value={name}
						onChange={(e) => setName(e.target.value)}
						placeholder="Defaults to “Subject - Platform”"
						className={inputClass}
					/>
				</div>
				<div className="flex-1">
					<label className={labelClass} htmlFor="description">Description (optional)</label>
					<input
						id="description"
						value={description}
						onChange={(e) => setDescription(e.target.value)}
						className={inputClass}
					/>
				</div>
			</div>

			{error && <p className="mt-3 text-sm text-red-500">{error}</p>}

			<div className="mt-4 flex items-center gap-2">
				<button
					type="submit"
					disabled={!canSubmit}
					className="cursor-pointer rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
				>
					{saving ? 'Adding…' : 'Add tracker'}
				</button>
				<button
					type="button"
					onClick={onCancel}
					className="cursor-pointer rounded-md px-3 py-2 text-sm text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
				>
					Cancel
				</button>
			</div>
		</form>
	);
}
