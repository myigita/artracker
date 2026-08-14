import { useState, useEffect } from 'react';
import type { Tracker } from '../api';
import { getTrackers } from '../api';
import TrackerCard from './TrackerCard';


export default function TrackerPanel() {

	const [trackers, setTrackers] = useState<Tracker[]>([]);
	function fetchTrackers() {
		getTrackers().then((data) => {
			setTrackers(data);
		});
	}

	useEffect(() => {
		fetchTrackers();
	}, []);

	const cards = trackers.map((tracker) => (
		<TrackerCard key={tracker.id} tracker={tracker} onChecked={fetchTrackers} />
	));

	return (
		<div className="mx-auto max-w-2xl p-6">
			<h2 className="mb-4 text-2xl font-semibold text-[var(--text-h)]">
				Trackers <span className="text-base font-normal text-[var(--text)]">({trackers.length})</span>
			</h2>
			<div className="flex flex-col gap-3">
				{cards}
			</div>
		</div>
	);
}