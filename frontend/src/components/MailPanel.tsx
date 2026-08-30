import { useEffect, useState } from 'react';
import type { PollResult, UnmatchedMail } from '../api';
import { dismissUnmatchedMail, errorDetail, getUnmatchedMail, pollMail } from '../api';

type Props = {
	// Polling can create updates, which changes every tracker's badge.
	onPolled: () => void;
};

export default function MailPanel({ onPolled }: Props) {
	const [unmatched, setUnmatched] = useState<UnmatchedMail[]>([]);
	const [polling, setPolling] = useState(false);
	const [result, setResult] = useState<PollResult | null>(null);
	const [error, setError] = useState<string | null>(null);

	function refresh() {
		return getUnmatchedMail().then(setUnmatched);
	}

	useEffect(() => {
		refresh().catch(() => setError('Could not load unmatched mail.'));
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
			// The backend's detail is worth showing verbatim here: a 503 names the
			// exact environment variables that are missing, and a 502 carries the
			// mail server's own complaint. A generic message would hide both.
			.catch((err) => setError(errorDetail(err) ?? 'Could not check the mailbox.'))
			.finally(() => setPolling(false));
	}

	function handleDismiss(id: number) {
		setError(null);
		dismissUnmatchedMail(id)
			.then(refresh)
			.catch(() => setError('Could not dismiss that message.'));
	}

	return (
		<div className="flex flex-col gap-6">
			<section>
				<h2 className="font-semibold text-[var(--text-h)]">Check for updates</h2>
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
				<h2 className="font-semibold text-[var(--text-h)]">Unmatched mail</h2>
				<p className="mt-1 text-sm text-[var(--text)]">
					Notifications that arrived but resolved to no tracker. This list is the
					reason a broken match doesn’t look like an artist who went quiet — each
					row says which step failed.
				</p>

				{unmatched.length === 0 ? (
					<p className="mt-3 rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--text)]">
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
									<span className="truncate font-medium text-[var(--text-h)]">
										{item.subject || '(no subject)'}
									</span>
									{/* Absolute rather than relative: this is a diagnostic view,
									    and "which message was that" is answered by a timestamp
									    you can match against the mailbox. */}
									<span className="ml-auto shrink-0 text-xs text-[var(--text)]">
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
								<p className="mt-1 truncate text-xs text-[var(--text)]">{item.sender}</p>
								<p className="mt-1 text-xs text-[var(--text)]">{item.reason}</p>
							</div>
						))}
					</div>
				)}
			</section>
		</div>
	);
}
