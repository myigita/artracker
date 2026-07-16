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
