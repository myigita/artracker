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

export type Subject = {
	id: number,
	name: string,
	date_created: string,
};

export type Platform = {
	id: number,
	name: string,
	date_created: string,
};

// What we SEND when creating. Optional fields use `?` (may be absent)
// rather than `| null` (always present, may be null) — mirrors TrackerIn.
export type TrackerIn = {
	subject_name: string,
	platform_name: string,
	url: string,
	description?: string,
	name?: string,
};

// PATCH payload: every field optional, only send what changed.
export type TrackerUpdate = {
	name?: string,
	url?: string,
	description?: string | null,
};

export async function getTrackers(): Promise<Tracker[]> {
	const response = await api.get<Tracker[]>('/trackers/');
	return response.data;
}

export async function checkTracker(id: number): Promise<Tracker> {
	const response = await api.post<Tracker>(`/trackers/${id}/check`);
	return response.data;
}

export async function deleteTracker(id: number): Promise<Tracker> {
	const response = await api.delete<Tracker>(`/trackers/${id}`);
	return response.data;
}

export async function createTracker(data: TrackerIn): Promise<Tracker> {
	const response = await api.post<Tracker>('/trackers/', data);
	return response.data;
}

export async function updateTracker(id: number, data: TrackerUpdate): Promise<Tracker> {
	const response = await api.patch<Tracker>(`/trackers/${id}`, data);
	return response.data;
}

export async function getSubjects(): Promise<Subject[]> {
	const response = await api.get<Subject[]>('/subjects/');
	return response.data;
}

export async function getPlatforms(): Promise<Platform[]> {
	const response = await api.get<Platform[]>('/platforms/');
	return response.data;
}

// The backend 409s when the name already exists. For our purposes that's a
// success — we only care that a subject/platform by this name exists after
// the call, not that we were the one to create it.
function ignoreConflict(error: unknown): void {
	if (axios.isAxiosError(error) && error.response?.status === 409) return;
	throw error;
}

export async function ensureSubject(name: string): Promise<void> {
	await api.post('/subjects/', { name }).catch(ignoreConflict);
}

export async function ensurePlatform(name: string): Promise<void> {
	await api.post('/platforms/', { name }).catch(ignoreConflict);
}
