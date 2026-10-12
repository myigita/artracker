import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export type MatchField = 'sender' | 'subject';

export type MatchOperator = 'contains' | 'not_contains' | 'equals' | 'not_equals';

export type MatchRule = {
	id: number,
	field: MatchField,
	operator: MatchOperator,
	value: string,
};

export type MatchRuleIn = {
	field: MatchField,
	operator: MatchOperator,
	value: string,
};

export type Tracker = {
	id: number,
	name: string,
	subject_name: string,
	subject_category: string | null,
	platform_name: string,
	url: string,
	description: string | null,
	rules: MatchRule[],
	date_created: string,
	last_checked: string | null,
	unread_count: number,
};

export type Subject = {
	id: number,
	name: string,
	category_name: string | null,
	date_created: string,
};

export type Platform = {
	id: number,
	name: string,
	mail_domain: string | null,
	is_preset: boolean,
	date_created: string,
};

export type Category = {
	id: number,
	name: string,
	date_created: string,
};

export type TrackerIn = {
	subject_name: string,
	platform_name: string,
	url: string,
	description?: string,
	name?: string,
	rules?: MatchRuleIn[],
};

export type TrackerUpdate = {
	name?: string,
	url?: string,
	description?: string | null,
	rules?: MatchRuleIn[],
	// null restores "never checked".
	last_checked?: string | null,
};

// null clears the category; omitting the key leaves it alone.
export type SubjectUpdate = {
	category_name?: string | null,
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

export async function deleteSubject(id: number): Promise<void> {
	await api.delete(`/subjects/${id}`);
}

export async function deletePlatform(id: number): Promise<void> {
	await api.delete(`/platforms/${id}`);
}

export async function deleteCategory(id: number): Promise<void> {
	await api.delete(`/categories/${id}`);
}


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

export async function importBackup(data: unknown, mode: ImportMode): Promise<ImportResult> {
	const response = await api.post<ImportResult>('/backup/import', data, { params: { mode } });
	return response.data;
}


export type Update = {
	id: number,
	tracker_id: number,
	summary: string | null,
	detected_at: string,
};

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

// No password field: the API never returns it.
export type MailAccount = {
	host: string,
	port: number,
	username: string,
	mailbox: string,
	has_password: boolean,
	source: 'database' | 'environment' | 'unset',
};

export type MailAccountIn = {
	host: string,
	port: number,
	username: string,
	mailbox: string,
	// Omitted entirely to keep the stored password.
	password?: string,
};

export async function getMailAccount(): Promise<MailAccount> {
	const response = await api.get<MailAccount>('/mail/account');
	return response.data;
}

export async function setMailAccount(data: MailAccountIn): Promise<MailAccount> {
	const response = await api.put<MailAccount>('/mail/account', data);
	return response.data;
}

export async function clearMailAccount(): Promise<void> {
	await api.delete('/mail/account');
}

export type PollSchedule = {
	enabled: boolean,
	interval_minutes: number,
	last_run_at: string | null,
	last_result: string | null,
	next_run_at: string | null,
};

export type PollScheduleIn = {
	enabled: boolean,
	interval_minutes: number,
};

export async function getPollSchedule(): Promise<PollSchedule> {
	const response = await api.get<PollSchedule>('/mail/schedule');
	return response.data;
}

export async function setPollSchedule(data: PollScheduleIn): Promise<PollSchedule> {
	const response = await api.put<PollSchedule>('/mail/schedule', data);
	return response.data;
}

export async function getTrackerUpdates(id: number): Promise<Update[]> {
	const response = await api.get<Update[]>(`/trackers/${id}/updates`);
	return response.data;
}

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
