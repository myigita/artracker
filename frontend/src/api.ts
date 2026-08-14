import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export type Tracker = {
	id: number,
	name: string,
	subject_name: string,
	platform_name: string,
	url: string,
	description: string | null,
	date_created: string,
	last_checked: string | null,
};

export async function getTrackers(): Promise<Tracker[]> {
	const response = await api.get<Tracker[]>('/trackers/');
	return response.data;
}

// Item routes take no trailing slash (collection routes do).
export async function checkTracker(id: number): Promise<Tracker> {
	const response = await api.post<Tracker>(`/trackers/${id}/check`);
	return response.data;
}
