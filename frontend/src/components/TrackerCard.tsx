import type { Tracker } from '../api';

type Props = {
	tracker: Tracker;
};

export default function TrackerCard({ tracker }: Props) {
	return (
		<div className="tracker-card">
			<h3>{tracker.name}</h3>
		</div>
	);
}
