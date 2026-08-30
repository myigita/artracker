import { useState, useRef } from 'react';
import type { ImportMode, ImportResult } from '../api';
import { exportBackup, importBackup, errorDetail } from '../api';

type Props = {
	// Re-fetch everything after an import — the whole database may have changed.
	onImported: () => void;
};

const buttonClass =
	'cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-opacity ' +
	'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40';

function today() {
	return new Date().toISOString().slice(0, 10);
}

export default function BackupPanel({ onImported }: Props) {
	// The <input type="file"> is uncontrolled — clearing the state above doesn't
	// clear what it displays, so after an import it would keep showing the
	// filename next to a disabled button and look stuck. Only the DOM node can
	// reset that.
	const fileInput = useRef<HTMLInputElement>(null);
	const [file, setFile] = useState<File | null>(null);
	const [mode, setMode] = useState<ImportMode>('merge');
	const [confirming, setConfirming] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [result, setResult] = useState<ImportResult | null>(null);

	function handleExport() {
		setBusy(true);
		setError(null);

		exportBackup()
			.then((data) => {
				// Build the file in memory and click a link at it. revokeObjectURL
				// matters: without it the blob is held for the life of the page.
				const blob = new Blob([JSON.stringify(data, null, 2)], {
					type: 'application/json',
				});
				const url = URL.createObjectURL(blob);
				const link = document.createElement('a');
				link.href = url;
				link.download = `artracker-backup-${today()}.json`;
				link.click();
				URL.revokeObjectURL(url);
			})
			.catch(() => setError('Could not export. Is the backend running?'))
			.finally(() => setBusy(false));
	}

	function chooseFile(chosen: File | null) {
		setFile(chosen);
		setResult(null);
		setError(null);
		// Any change invalidates a pending "are you sure?" — otherwise you could
		// confirm one file and import a different one.
		setConfirming(false);
	}

	function chooseMode(chosen: ImportMode) {
		setMode(chosen);
		setConfirming(false);
	}

	function handleImport() {
		if (!file) return;

		// Replace deletes everything first, so it takes a second, explicit click.
		if (mode === 'replace' && !confirming) {
			setConfirming(true);
			return;
		}

		setBusy(true);
		setError(null);
		setResult(null);

		file
			.text()
			.then((text) => importBackup(JSON.parse(text), mode))
			.then((imported) => {
				setResult(imported);
				setConfirming(false);
				setFile(null);
				if (fileInput.current) fileInput.current.value = '';
				onImported();
			})
			.catch((err) => {
				setConfirming(false);
				if (err instanceof SyntaxError) {
					setError("That file isn't valid JSON.");
					return;
				}
				setError(errorDetail(err) ?? 'Could not import that file.');
			})
			.finally(() => setBusy(false));
	}

	return (
		<div className="flex flex-col gap-4">
			<section className="rounded-lg border border-[var(--border)] p-4">
				<h3 className="font-semibold text-[var(--text-h)]">Export</h3>
				<p className="mt-1 text-sm text-[var(--text)]">
					Downloads everything — trackers, subjects, platforms and categories —
					as one JSON file.
				</p>
				<button
					type="button"
					onClick={handleExport}
					disabled={busy}
					className={`${buttonClass} mt-3 bg-[var(--accent)] text-white`}
				>
					Download backup
				</button>
			</section>

			<section className="rounded-lg border border-[var(--border)] p-4">
				<h3 className="font-semibold text-[var(--text-h)]">Import</h3>

				<input
					ref={fileInput}
					type="file"
					accept="application/json,.json"
					onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
					aria-label="Backup file to import"
					className="mt-3 block w-full text-sm text-[var(--text)] file:mr-3 file:cursor-pointer file:rounded-md file:border file:border-[var(--border)] file:bg-transparent file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[var(--text-h)] hover:file:border-[var(--accent-border)]"
				/>

				<fieldset className="mt-4">
					<legend className="text-xs font-medium text-[var(--text)]">
						What to do with the data already here
					</legend>
					<label className="mt-2 flex items-start gap-2 text-sm text-[var(--text-h)]">
						<input
							type="radio"
							name="import-mode"
							checked={mode === 'merge'}
							onChange={() => chooseMode('merge')}
							className="mt-1 accent-[var(--accent)]"
						/>
						<span>
							Merge
							<span className="block text-xs text-[var(--text)]">
								Adds what's missing. Anything already here is left alone.
							</span>
						</span>
					</label>
					<label className="mt-2 flex items-start gap-2 text-sm text-[var(--text-h)]">
						<input
							type="radio"
							name="import-mode"
							checked={mode === 'replace'}
							onChange={() => chooseMode('replace')}
							className="mt-1 accent-[var(--accent)]"
						/>
						<span>
							Replace
							<span className="block text-xs text-[var(--text)]">
								Deletes everything here first, then restores the file exactly.
							</span>
						</span>
					</label>
				</fieldset>

				{confirming && (
					<p className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-[var(--text-h)]">
						This deletes every tracker, subject, platform and category currently
						in the app, then restores the file. Click Replace again to go ahead.
					</p>
				)}

				<button
					type="button"
					onClick={handleImport}
					disabled={!file || busy}
					className={`${buttonClass} mt-3 ${
						mode === 'replace'
							? 'bg-red-600 text-white'
							: 'bg-[var(--accent)] text-white'
					}`}
				>
					{busy
						? 'Importing…'
						: mode === 'replace'
							? confirming
								? 'Yes, replace everything'
								: 'Replace'
							: 'Merge'}
				</button>

				{error && <p className="mt-3 text-sm text-red-500">{error}</p>}

				{result && (
					<p className="mt-3 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg)] px-3 py-2 text-sm text-[var(--text-h)]">
						Imported in {result.mode} mode: {result.trackers_added} tracker(s),{' '}
						{result.subjects_added} subject(s), {result.platforms_added}{' '}
						platform(s), {result.categories_added} category(ies) added
						{result.skipped > 0 && `, ${result.skipped} already present`}
						{result.deleted > 0 && `, ${result.deleted} row(s) replaced`}.
					</p>
				)}
			</section>
		</div>
	);
}
