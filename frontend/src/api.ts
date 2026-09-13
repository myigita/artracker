import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

// Which part of a message a rule looks at. The body is deliberately not an
// option: headers are already in hand after a fetch, bodies mean parsing
// multipart HTML, and that's where false positives live.
export type MatchField = 'sender' | 'subject';

// The negative forms are what make a broad sender rule usable — "from Patreon,
// but not the weekly digest".
export type MatchOperator = 'contains' | 'not_contains' | 'equals' | 'not_equals';

export type MatchRule = {
	id: number,
	field: MatchField,
	operator: MatchOperator,
	value: string,
};

// What we SEND. No id — rules are replaced wholesale rather than patched
// individually, so the server assigns them fresh each time.
export type MatchRuleIn = {
	field: MatchField,
	operator: MatchOperator,
	value: string,
};

export type Tracker = {
	id: number,
	name: string,
	subject_name: string,
	// The category of this tracker's subject, or null if it has none.
	subject_category: string | null,
	platform_name: string,
	url: string,
	description: string | null,
	// Conditions incoming mail must satisfy to land on this tracker.
	rules: MatchRule[],
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
	date_created: string,
};

export type Platform = {
	id: number,
	name: string,
	// Sender domain of this platform's notification mail, or null for a plain
	// saved link with no automatic updates.
	mail_domain: string | null,
	// Seeded by the app and refused deletion — the backend recreates it on every
	// start, so deleting would only appear to work.
	is_preset: boolean,
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
	// Omitted and [] both mean no rules. Platform domains are deliberately not
	// defaults because one domain is shared by every artist on that platform.
	rules?: MatchRuleIn[],
};

// PATCH payload: every field optional, only send what changed.
export type TrackerUpdate = {
	name?: string,
	url?: string,
	description?: string | null,
	// Replaced wholesale, like the create payload. Omitting the key leaves the
	// rules alone; [] clears them, which the server refuses when there's no URL
	// to fall back on.
	rules?: MatchRuleIn[],
	// Send back the exact string the API gave us to undo a check. null restores
	// a tracker that had never been checked.
	last_checked?: string | null,
};

// Unlike TrackerUpdate, null here is meaningful rather than just permitted:
// null clears the subject's category, while omitting the key leaves it alone.
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

// Note the absence of a password field: the API never sends one back. The form
// starts blank and only submits a password when the user is actually changing it.
export type MailAccount = {
	host: string,
	port: number,
	username: string,
	mailbox: string,
	has_password: boolean,
	// Where the mailbox currently in effect came from. "environment" means the
	// container was configured with ARTRACKER_MAIL_* and nothing is stored.
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

// The background poller's schedule. Five minutes is the server-side floor.
export type PollSchedule = {
	enabled: boolean,
	interval_minutes: number,
	last_run_at: string | null,
	// One line about the last pass, or the error it failed with. A background
	// poller has no request to watch fail, so this is the only feedback there is.
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
