import { useEffect, useState } from 'react';
import type { MailAccount, PollResult, PollSchedule, UnmatchedMail } from '../api';
import {
	clearMailAccount,
	dismissUnmatchedMail,
	errorDetail,
	getMailAccount,
	getPollSchedule,
	getUnmatchedMail,
	pollMail,
	setMailAccount,
} from '../api';
import MailboxForm from './MailboxForm';
import PollScheduleForm from './PollScheduleForm';
import SettingsGroup from './SettingsGroup';
import ThemePicker from './ThemePicker';
import Collapse, { Chevron } from './Collapse';

type Props = {
	onPolled: () => void;
};

export default function SettingsPanel({ onPolled }: Props) {
	const [unmatched, setUnmatched] = useState<UnmatchedMail[]>([]);
	const [account, setAccount] = useState<MailAccount | null>(null);
	const [schedule, setSchedule] = useState<PollSchedule | null>(null);
	const [polling, setPolling] = useState(false);
	const [result, setResult] = useState<PollResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [showUnmatched, setShowUnmatched] = useState(false);

	function refresh() {
		return getUnmatchedMail().then(setUnmatched);
	}

	useEffect(() => {
		refresh().catch(() => setError('Could not load unmatched mail.'));
		getMailAccount().then(setAccount).catch(() => setAccount(null));
		getPollSchedule().then(setSchedule).catch(() => setSchedule(null));
	}, []);

	function handlePoll() {
		setPolling(true);
		setError(null);
		setResult(null);

		pollMail()
			.then((outcome) => {
				setResult(outcome);
				onPolled();
				return refresh();
			})
			.catch((err) => setError(errorDetail(err) ?? 'Could not check the mailbox.'))
			.finally(() => {
				setPolling(false);
				getPollSchedule().then(setSchedule).catch(() => {});
			});
	}

	function handleDismiss(id: number) {
		setError(null);
		dismissUnmatchedMail(id)
			.then(refresh)
			.catch(() => setError('Could not dismiss that message.'));
	}

	return (
		<div className="flex flex-col gap-6">
			<SettingsGroup
				title="Mail setup"
				description="Where notifications arrive, and how often Artracker reads them."
			>
				<MailboxForm
					account={account}
					onSaved={(saved) => {
						setAccount(saved);
						setResult(null);
					}}
					onSave={setMailAccount}
					onClear={clearMailAccount}
					onCleared={() => getMailAccount().then(setAccount)}
				/>

				<PollScheduleForm schedule={schedule} onSaved={setSchedule} />
			</SettingsGroup>

			<SettingsGroup
				title="Activity"
				description="Check the mailbox by hand, and review mail no tracker claimed."
			>
				<section>
					<h3 className="font-semibold text-[var(--text-h)]">Check now</h3>
					<p className="mt-1 text-sm text-[var(--text)]">
						Reads the gathering mailbox and records an update for every notification
						that matches a tracker. Safe to run as often as you like — messages
						already seen are ignored.
					</p>
					<button
						type="button"
						onClick={handlePoll}
						disabled={polling}
						className="mt-3 cursor-pointer rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
					>
						{polling ? 'Checking…' : 'Check mail now'}
					</button>

					{result && (
						<p className="mt-3 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg)] px-3 py-2 text-sm text-[var(--text-h)]">
							Read {result.fetched} message{result.fetched === 1 ? '' : 's'}:{' '}
							{result.recorded} recorded, {result.duplicates} already seen,{' '}
							{result.unmatched} unmatched.
						</p>
					)}

					{error && (
						<p className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-[var(--text-h)]">
							{error}
						</p>
					)}
				</section>

				<section>
					<h3>
						<button
							type="button"
							onClick={() => setShowUnmatched((value) => !value)}
							aria-expanded={showUnmatched}
							aria-controls="unmatched-mail-list"
							className="flex w-full cursor-pointer items-center gap-2 text-left font-semibold text-[var(--text-h)]"
						>
							Unmatched mail
							<span className="text-sm font-normal text-[var(--text)]">· {unmatched.length}</span>
							<span className="ml-auto text-[var(--text)]">
								<Chevron open={showUnmatched} />
							</span>
						</button>
					</h3>
					<p className="mt-1 text-sm text-[var(--text)]">
						Notifications that arrived but resolved to no tracker. This list is the
						reason a broken match doesn’t look like an artist who went quiet — each
						row says which step failed.
					</p>

					<Collapse open={showUnmatched} id="unmatched-mail-list">
						{unmatched.length === 0 ? (
							<p className="mt-3 rounded-lg border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--text)]">
								Nothing unmatched.
							</p>
						) : (
							<div className="mt-3 flex flex-col gap-2">
								{unmatched.map((item) => (
									<div
										key={item.id}
										className="rounded-lg border border-[var(--border)] px-4 py-3"
									>
										<div className="flex items-baseline gap-3">
											<span className="min-w-0 flex-1 truncate font-medium text-[var(--text-h)]">
												{item.subject || '(no subject)'}
											</span>
											<span className="hidden shrink-0 text-xs text-[var(--text)] sm:inline">
												{new Date(item.received_at).toLocaleString()}
											</span>
											<button
												type="button"
												onClick={() => handleDismiss(item.id)}
												aria-label={`Dismiss the unmatched message from ${item.sender}`}
												className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-red-500 focus-visible:text-red-500"
											>
												<svg
													width="16"
													height="16"
													viewBox="0 0 24 24"
													fill="none"
													stroke="currentColor"
													strokeWidth="2"
													aria-hidden="true"
												>
													<path d="M18 6L6 18M6 6l12 12" />
												</svg>
											</button>
										</div>
										<p className="mt-1 flex flex-wrap gap-x-1 text-xs text-[var(--text)]">
											<span className="min-w-0 truncate">{item.sender}</span>
											<span className="sm:hidden">· {new Date(item.received_at).toLocaleString()}</span>
										</p>
										<p className="mt-1 text-xs text-[var(--text)]">{item.reason}</p>
									</div>
								))}
							</div>
						)}
					</Collapse>
				</section>
			</SettingsGroup>

			<SettingsGroup title="Appearance" description="How Artracker looks on this device.">
				<ThemePicker />
			</SettingsGroup>
		</div>
	);
}
