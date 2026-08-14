import { useState, useEffect } from 'react';
import type { Tracker } from '../api';
import { getTrackers, createSubject, createPlatform } from '../api';
import TrackerCard from './TrackerCard';
import AddTrackerForm from './AddTrackerForm';
import AddNameForm from './AddNameForm';

// Only one form is open at a time, so a single value beats three booleans —
// it makes "these are mutually exclusive" true by construction.
type OpenForm = 'tracker' | 'subject' | 'platform' | null;

export default function TrackerPanel() {

	const [trackers, setTrackers] = useState<Tracker[]>([]);
	const [openForm, setOpenForm] = useState<OpenForm>(null);
	const [notice, setNotice] = useState<string | null>(null);

	function fetchTrackers() {
		getTrackers().then((data) => {
			setTrackers(data);
		});
	}

	useEffect(() => {
		fetchTrackers();
	}, []);

	function handleAdded() {
		setOpenForm(null);
		fetchTrackers();
	}

	function handleNameCreated(kind: string, name: string) {
		setOpenForm(null);
		// No refetch needed — trackers are unaffected. The tracker form picks up
		// the new option because it refetches its dropdowns when it opens.
		setNotice(`Added ${kind} “${name}”.`);
	}

	function openFormAndClearNotice(form: OpenForm) {
		setNotice(null);
		setOpenForm(form);
	}

	const buttonClass =
		'cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-opacity hover:opacity-90';

	const cards = trackers.map((tracker) => (
		<TrackerCard
			key={tracker.id}
			tracker={tracker}
			onChecked={fetchTrackers}
			onDeleted={fetchTrackers}
			onUpdated={fetchTrackers}
		/>
	));

	return (
		<div className="mx-auto max-w-2xl p-6">
			<div className="mb-4 flex flex-wrap items-center gap-2">
				<h2 className="mr-auto text-2xl font-semibold text-[var(--text-h)]">
					Trackers <span className="text-base font-normal text-[var(--text)]">({trackers.length})</span>
				</h2>
				{openForm === null && (
					<>
						<button
							type="button"
							onClick={() => openFormAndClearNotice('subject')}
							className={`${buttonClass} border border-[var(--border)] text-[var(--text)] hover:text-[var(--text-h)]`}
						>
							+ Subject
						</button>
						<button
							type="button"
							onClick={() => openFormAndClearNotice('platform')}
							className={`${buttonClass} border border-[var(--border)] text-[var(--text)] hover:text-[var(--text-h)]`}
						>
							+ Platform
						</button>
						<button
							type="button"
							onClick={() => openFormAndClearNotice('tracker')}
							className={`${buttonClass} bg-[var(--accent)] text-white`}
						>
							+ Add tracker
						</button>
					</>
				)}
			</div>

			{notice && (
				<p className="mb-4 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg)] px-3 py-2 text-sm text-[var(--text-h)]">
					{notice}
				</p>
			)}

			{openForm === 'tracker' && (
				<AddTrackerForm onAdded={handleAdded} onCancel={() => setOpenForm(null)} />
			)}

			{openForm === 'subject' && (
				<AddNameForm
					label="Subject"
					onCreate={createSubject}
					onCreated={(name) => handleNameCreated('subject', name)}
					onCancel={() => setOpenForm(null)}
				/>
			)}

			{openForm === 'platform' && (
				<AddNameForm
					label="Platform"
					onCreate={createPlatform}
					onCreated={(name) => handleNameCreated('platform', name)}
					onCancel={() => setOpenForm(null)}
				/>
			)}

			<div className="flex flex-col gap-3">
				{cards}
			</div>

			{trackers.length === 0 && openForm === null && (
				<p className="rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
					No trackers yet — add your first one to get started.
				</p>
			)}
		</div>
	);
}