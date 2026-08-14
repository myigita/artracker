import { useState, useEffect } from 'react';
import type { Tracker, Subject, Platform, Category } from '../api';
import {
	getTrackers,
	getSubjects,
	getPlatforms,
	getCategories,
	createSubject,
	createPlatform,
	createCategory,
	deleteSubject,
	deletePlatform,
	deleteCategory,
} from '../api';
import TrackerCard from './TrackerCard';
import AddTrackerForm from './AddTrackerForm';
import AddNameForm from './AddNameForm';
import NameList from './NameList';
import SubjectCategorySelect from './SubjectCategorySelect';

// Only one form is open at a time, so a single value beats four booleans —
// it makes "these are mutually exclusive" true by construction.
type OpenForm = 'tracker' | 'subject' | 'platform' | 'category' | null;
type Tab = 'trackers' | 'subjects' | 'platforms' | 'categories';

const TABS: { id: Tab; label: string }[] = [
	{ id: 'trackers', label: 'Trackers' },
	{ id: 'subjects', label: 'Subjects' },
	{ id: 'platforms', label: 'Platforms' },
	{ id: 'categories', label: 'Categories' },
];

export default function TrackerPanel() {

	const [trackers, setTrackers] = useState<Tracker[]>([]);
	const [subjects, setSubjects] = useState<Subject[]>([]);
	const [platforms, setPlatforms] = useState<Platform[]>([]);
	const [categories, setCategories] = useState<Category[]>([]);
	const [tab, setTab] = useState<Tab>('trackers');
	const [openForm, setOpenForm] = useState<OpenForm>(null);
	const [notice, setNotice] = useState<string | null>(null);
	// "No trackers yet" and "couldn't reach the server" both render an empty
	// list, so the empty state MUST be able to tell them apart — otherwise a
	// dead backend looks exactly like a deleted database.
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState(false);

	function fetchTrackers() {
		return getTrackers().then((data) => {
			setTrackers(data);
		});
	}

	function fetchSubjects() {
		return getSubjects().then(setSubjects);
	}

	function fetchPlatforms() {
		return getPlatforms().then(setPlatforms);
	}

	function fetchCategories() {
		return getCategories().then(setCategories);
	}

	function fetchAll() {
		setLoadError(false);
		return Promise.all([
			fetchTrackers(),
			fetchSubjects(),
			fetchPlatforms(),
			fetchCategories(),
		])
			.catch(() => setLoadError(true))
			.finally(() => setLoading(false));
	}

	useEffect(() => {
		fetchAll();
	}, []);

	function handleAdded() {
		setOpenForm(null);
		fetchAll();
	}

	function handleNameCreated(kind: string, name: string) {
		setOpenForm(null);
		Promise.all([fetchSubjects(), fetchPlatforms(), fetchCategories()]).catch(() =>
			setLoadError(true),
		);
		setNotice(`Added ${kind} “${name}”.`);
	}

	// Trackers carry subject_name/platform_name, so usage counts come straight
	// off the list already in state — no extra endpoint needed.
	function subjectUsage(name: string) {
		return trackers.filter((t) => t.subject_name === name).length;
	}

	function platformUsage(name: string) {
		return trackers.filter((t) => t.platform_name === name).length;
	}

	// A category is used by subjects, not trackers — same idea, different list.
	function categoryUsage(name: string) {
		return subjects.filter((s) => s.category_name === name).length;
	}

	function openFormAndClearNotice(form: OpenForm) {
		setNotice(null);
		setOpenForm(form);
	}

	const buttonClass =
		'cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-opacity hover:opacity-90';

	const counts: Record<Tab, number> = {
		trackers: trackers.length,
		subjects: subjects.length,
		platforms: platforms.length,
		categories: categories.length,
	};

	// The "+ Add" button follows whichever tab you're on.
	const addFormFor: Record<Tab, OpenForm> = {
		trackers: 'tracker',
		subjects: 'subject',
		platforms: 'platform',
		categories: 'category',
	};

	const addLabel: Record<Tab, string> = {
		trackers: '+ Add tracker',
		subjects: '+ Add subject',
		platforms: '+ Add platform',
		categories: '+ Add category',
	};

	const cards = trackers.map((tracker) => (
		<TrackerCard
			key={tracker.id}
			tracker={tracker}
			onChecked={fetchTrackers}
			onDeleted={fetchTrackers}
			onUpdated={fetchTrackers}
		/>
	));

	return (
		<div className="mx-auto max-w-2xl p-6">
			<div className="mb-4 flex flex-wrap items-center gap-2">
				<div className="mr-auto flex gap-1" role="tablist">
					{TABS.map(({ id, label }) => (
						<button
							key={id}
							type="button"
							role="tab"
							aria-selected={tab === id}
							onClick={() => {
								setTab(id);
								setOpenForm(null);
								setNotice(null);
							}}
							className={`cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-colors ${
								tab === id
									? 'bg-[var(--accent-bg)] text-[var(--text-h)]'
									: 'text-[var(--text)] hover:text-[var(--text-h)]'
							}`}
						>
							{label}{' '}
							<span className="text-xs font-normal">({counts[id]})</span>
						</button>
					))}
				</div>

				{openForm === null && (
					<button
						type="button"
						onClick={() => openFormAndClearNotice(addFormFor[tab])}
						className={`${buttonClass} bg-[var(--accent)] text-white`}
					>
						{addLabel[tab]}
					</button>
				)}
			</div>

			{notice && (
				<p className="mb-4 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg)] px-3 py-2 text-sm text-[var(--text-h)]">
					{notice}
				</p>
			)}

			{openForm === 'tracker' && (
				<AddTrackerForm onAdded={handleAdded} onCancel={() => setOpenForm(null)} />
			)}

			{openForm === 'subject' && (
				<AddNameForm
					label="Subject"
					onCreate={createSubject}
					onCreated={(name) => handleNameCreated('subject', name)}
					onCancel={() => setOpenForm(null)}
				/>
			)}

			{openForm === 'platform' && (
				<AddNameForm
					label="Platform"
					onCreate={createPlatform}
					onCreated={(name) => handleNameCreated('platform', name)}
					onCancel={() => setOpenForm(null)}
				/>
			)}

			{openForm === 'category' && (
				<AddNameForm
					label="Category"
					onCreate={createCategory}
					onCreated={(name) => handleNameCreated('category', name)}
					onCancel={() => setOpenForm(null)}
				/>
			)}

			{loadError && (
				<div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-[var(--text-h)]">
					<p className="font-medium">Couldn’t reach the server.</p>
					<p className="mt-1 text-[var(--text)]">
						Your data is probably fine — this page just can’t load it right now.
					</p>
					<button
						type="button"
						onClick={() => {
							setLoading(true);
							fetchAll();
						}}
						className="mt-3 cursor-pointer rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--text-h)] transition-colors hover:border-[var(--accent-border)]"
					>
						Retry
					</button>
				</div>
			)}

			{loading && !loadError && (
				<p className="p-8 text-center text-sm text-[var(--text)]">Loading…</p>
			)}

			{!loading && !loadError && tab === 'trackers' && (
				<>
					<div className="flex flex-col gap-3">{cards}</div>
					{trackers.length === 0 && openForm === null && (
						<p className="rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
							No trackers yet — add your first one to get started.
						</p>
					)}
				</>
			)}

			{!loading && !loadError && tab === 'subjects' && (
				<NameList
					label="Subject"
					items={subjects}
					usageCount={subjectUsage}
					renderExtra={(subject) => (
						<SubjectCategorySelect
							subject={subject}
							categories={categories}
							onChanged={fetchSubjects}
						/>
					)}
					onDelete={deleteSubject}
					onDeleted={fetchSubjects}
				/>
			)}

			{!loading && !loadError && tab === 'platforms' && (
				<NameList
					label="Platform"
					items={platforms}
					usageCount={platformUsage}
					onDelete={deletePlatform}
					onDeleted={fetchPlatforms}
				/>
			)}

			{!loading && !loadError && tab === 'categories' && (
				<NameList
					label="Category"
					items={categories}
					usageCount={categoryUsage}
					usageLabel="subject"
					plural="categories"
					blockedHint="Reassign those first."
					onDelete={deleteCategory}
					onDeleted={fetchCategories}
				/>
			)}
		</div>
	);
}