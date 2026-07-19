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
		<TrackerCard key={tracker.id} tracker={tracker} />
	));

	return (
		<div className="tracker-panel">
			<h2>Trackers</h2>
			<p>Length of trackers: {trackers.length}</p>
			<div className="tracker-cards">
				{cards}
			</div>
		</div>
	);
}