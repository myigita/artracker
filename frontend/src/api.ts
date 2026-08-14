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

export async function createSubject(name: string): Promise<Subject> {
	const response = await api.post<Subject>('/subjects/', { name });
	return response.data;
}

export async function createPlatform(name: string): Promise<Platform> {
	const response = await api.post<Platform>('/platforms/', { name });
	return response.data;
}

// The backend 409s when the name already exists. Whether that's an error
// depends on intent: pressing "Add subject" and being told it exists is
// useful feedback, but the tracker form only needs the name to EXIST — it
// doesn't care who created it. Hence two flavours.
// These return 204 No Content — there's no body to parse, hence no <T> and
// no `return response.data` (unlike deleteTracker, which returns the row).
// They 409 if any tracker still references the subject/platform.
export async function deleteSubject(id: number): Promise<void> {
	await api.delete(`/subjects/${id}`);
}

export async function deletePlatform(id: number): Promise<void> {
	await api.delete(`/platforms/${id}`);
}

export function isConflict(error: unknown): boolean {
	return axios.isAxiosError(error) && error.response?.status === 409;
}

function ignoreConflict(error: unknown): void {
	if (isConflict(error)) return;
	throw error;
}

export async function ensureSubject(name: string): Promise<void> {
	await createSubject(name).catch(ignoreConflict);
}

export async function ensurePlatform(name: string): Promise<void> {
	await createPlatform(name).catch(ignoreConflict);
}
