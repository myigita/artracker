import { useState, useEffect } from 'react';
import type { Tracker } from '../api';
import { getTrackers } from '../api';
import TrackerCard from './TrackerCard';
import AddTrackerForm from './AddTrackerForm';


export default function TrackerPanel() {

	const [trackers, setTrackers] = useState<Tracker[]>([]);
	const [showForm, setShowForm] = useState(false);

	function fetchTrackers() {
		getTrackers().then((data) => {
			setTrackers(data);
		});
	}

	useEffect(() => {
		fetchTrackers();
	}, []);

	function handleAdded() {
		setShowForm(false);
		fetchTrackers();
	}

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
			<div className="mb-4 flex items-center gap-3">
				<h2 className="text-2xl font-semibold text-[var(--text-h)]">
					Trackers <span className="text-base font-normal text-[var(--text)]">({trackers.length})</span>
				</h2>
				{!showForm && (
					<button
						type="button"
						onClick={() => setShowForm(true)}
						className="ml-auto cursor-pointer rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
					>
						+ Add tracker
					</button>
				)}
			</div>

			{showForm && (
				<AddTrackerForm onAdded={handleAdded} onCancel={() => setShowForm(false)} />
			)}

			<div className="flex flex-col gap-3">
				{cards}
			</div>

			{trackers.length === 0 && !showForm && (
				<p className="rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
					No trackers yet — add your first one to get started.
				</p>
			)}
		</div>
	);
}