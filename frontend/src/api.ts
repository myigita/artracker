import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export type Tracker = {
	id: number,
	name: string,
	subject_name: string,
	// The category of this tracker's subject, or null if it has none.
	subject_category: string | null,
	platform_name: string,
	url: string,
	description: string | null,
	date_created: string,
	last_checked: string | null,
	// Updates detected since last_checked. Computed by the backend, so it drops
	// to 0 the moment a check lands — no client-side bookkeeping.
	unread_count: number,
};

export type Subject = {
	id: number,
	name: string,
	category_name: string | null,
	// What this subject is called on the platforms it posts to, lowercased by the
	// backend. Matched against the local part of a notification email's sender.
	handles: string[],
	date_created: string,
};

export type Platform = {
	id: number,
	name: string,
	// Sender domain of this platform's notification mail, or null for a plain
	// saved link with no automatic updates.
	mail_domain: string | null,
	date_created: string,
};

export type Category = {
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
	// Send back the exact string the API gave us to undo a check. null restores
	// a tracker that had never been checked.
	last_checked?: string | null,
};

// Unlike TrackerUpdate, null here is meaningful rather than just permitted:
// null clears the subject's category, while omitting the key leaves it alone.
export type SubjectUpdate = {
	category_name?: string | null,
	// Sent whole, never incrementally: [] clears every handle, omitting the key
	// leaves them untouched.
	handles?: string[],
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

export async function getCategories(): Promise<Category[]> {
	const response = await api.get<Category[]>('/categories/');
	return response.data;
}

export async function updateSubject(id: number, data: SubjectUpdate): Promise<Subject> {
	const response = await api.patch<Subject>(`/subjects/${id}`, data);
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

export async function createCategory(name: string): Promise<Category> {
	const response = await api.post<Category>('/categories/', { name });
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

// 409s if any *subject* still points at the category — subjects are what use a
// category, the way trackers are what use a subject.
export async function deleteCategory(id: number): Promise<void> {
	await api.delete(`/categories/${id}`);
}

// ---- Backup / restore ------------------------------------------------------

export type ImportMode = 'merge' | 'replace';

export type ImportResult = {
	mode: ImportMode,
	categories_added: number,
	platforms_added: number,
	subjects_added: number,
	trackers_added: number,
	skipped: number,
	deleted: number,
};

export async function exportBackup(): Promise<unknown> {
	const response = await api.get('/backup/export');
	return response.data;
}

// The payload is whatever was in the file the user picked, so it stays
// `unknown` here rather than being asserted into a shape we haven't checked.
// The backend validates it and 422s on anything malformed.
export async function importBackup(data: unknown, mode: ImportMode): Promise<ImportResult> {
	const response = await api.post<ImportResult>('/backup/import', data, { params: { mode } });
	return response.data;
}

// ---- Notification mail -----------------------------------------------------

export type Update = {
	id: number,
	tracker_id: number,
	summary: string | null,
	detected_at: string,
};

// Mail that arrived but resolved to no tracker. Surfaced rather than dropped:
// sender addresses and subject formats change without warning, and silently
// discarded mail looks exactly like an artist who stopped posting.
export type UnmatchedMail = {
	id: number,
	sender: string,
	subject: string | null,
	reason: string,
	received_at: string,
};

export type PollResult = {
	fetched: number,
	recorded: number,
	duplicates: number,
	unmatched: number,
};

export async function getTrackerUpdates(id: number): Promise<Update[]> {
	const response = await api.get<Update[]>(`/trackers/${id}/updates`);
	return response.data;
}

// 503 when the mailbox env vars aren't set, 502 when the mailbox can't be read —
// both carry a `detail` worth showing, hence errorDetail at the call site.
export async function pollMail(): Promise<PollResult> {
	const response = await api.post<PollResult>('/mail/poll');
	return response.data;
}

export async function getUnmatchedMail(): Promise<UnmatchedMail[]> {
	const response = await api.get<UnmatchedMail[]>('/mail/unmatched');
	return response.data;
}

export async function dismissUnmatchedMail(id: number): Promise<void> {
	await api.delete(`/mail/unmatched/${id}`);
}

export function errorDetail(error: unknown): string | null {
	if (!axios.isAxiosError(error)) return null;
	const detail = error.response?.data?.detail;
	return typeof detail === 'string' ? detail : null;
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
