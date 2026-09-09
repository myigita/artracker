import { useEffect, useState } from 'react';
import type { MailAccount, MailAccountIn } from '../api';
import { errorDetail } from '../api';

type Props = {
	// null while loading, so the form doesn't flash empty fields at a configured
	// mailbox and invite someone to overwrite it with blanks.
	account: MailAccount | null;
	onSave: (data: MailAccountIn) => Promise<MailAccount>;
	onSaved: (account: MailAccount) => void;
	onClear: () => Promise<void>;
	onCleared: () => void;
};

const inputClass =
	'w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm ' +
	'text-[var(--text-h)] outline-none transition-colors focus:border-[var(--accent-border)] ' +
	'disabled:opacity-40';

const labelClass = 'block text-xs font-medium text-[var(--text)]';

export default function MailboxForm({ account, onSave, onSaved, onClear, onCleared }: Props) {
	const [host, setHost] = useState('');
	const [port, setPort] = useState(993);
	const [username, setUsername] = useState('');
	const [mailbox, setMailbox] = useState('INBOX');
	// Always starts blank. The API never sends the password back, so an empty box
	// means "leave it alone" rather than "there isn't one".
	const [password, setPassword] = useState('');
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [saved, setSaved] = useState(false);

	useEffect(() => {
		if (!account) return;
		setHost(account.host);
		setPort(account.port);
		setUsername(account.username);
		setMailbox(account.mailbox);
	}, [account]);

	function handleSubmit(event: React.FormEvent) {
		event.preventDefault();

		setSaving(true);
		setError(null);
		setSaved(false);

		const payload: MailAccountIn = { host, port, username, mailbox };
		// Sent only when non-empty, which is what lets the host be edited without
		// retyping the password.
		if (password) payload.password = password;

		onSave(payload)
			.then((result) => {
				setPassword('');
				setSaved(true);
				onSaved(result);
			})
			.catch((err) => setError(errorDetail(err) ?? 'Could not save the mailbox.'))
			.finally(() => setSaving(false));
	}

	function handleClear() {
		setError(null);
		setSaved(false);
		onClear()
			.then(() => {
				setPassword('');
				onCleared();
			})
			.catch((err) => setError(errorDetail(err) ?? 'Could not clear the mailbox.'));
	}

	const storedHere = account?.source === 'database';
	const fromEnvironment = account?.source === 'environment';
	// A first save has nothing stored to fall back on, so the password is required.
	const needsPassword = !account?.has_password && !password;

	return (
		<section>
			<h2 className="font-semibold text-[var(--text-h)]">Mailbox</h2>
			<p className="mt-1 text-sm text-[var(--text)]">
				The gathering account that platform notifications are forwarded to. Use a
				dedicated mailbox that receives nothing else — an app password grants full
				access to whatever account you point this at.
			</p>

			{fromEnvironment && (
				<p className="mt-2 rounded-md border border-[var(--border)] px-3 py-2 text-xs text-[var(--text)]">
					Currently coming from the <code>ARTRACKER_MAIL_*</code> environment
					variables. Saving here stores a mailbox in the database, which takes
					precedence from then on.
				</p>
			)}

			<form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3">
				<div className="flex flex-col gap-3 sm:flex-row">
					<div className="flex-1">
						<label className={labelClass} htmlFor="mail-host">
							IMAP server
						</label>
						<input
							id="mail-host"
							value={host}
							required
							disabled={saving}
							onChange={(event) => setHost(event.target.value)}
							placeholder="imap.gmail.com"
							className={`${inputClass} mt-1`}
						/>
					</div>
					<div className="sm:w-24">
						<label className={labelClass} htmlFor="mail-port">
							Port
						</label>
						<input
							id="mail-port"
							type="number"
							value={port}
							required
							disabled={saving}
							onChange={(event) => setPort(Number(event.target.value))}
							className={`${inputClass} mt-1`}
						/>
					</div>
				</div>

				<div>
					<label className={labelClass} htmlFor="mail-username">
						Username
					</label>
					<input
						id="mail-username"
						value={username}
						required
						disabled={saving}
						onChange={(event) => setUsername(event.target.value)}
						placeholder="gather@example.com"
						className={`${inputClass} mt-1`}
					/>
				</div>

				<div>
					<label className={labelClass} htmlFor="mail-password">
						Password
					</label>
					<input
						id="mail-password"
						type="password"
						value={password}
						disabled={saving}
						onChange={(event) => setPassword(event.target.value)}
						autoComplete="new-password"
						placeholder={account?.has_password ? 'Unchanged' : 'App password'}
						className={`${inputClass} mt-1`}
					/>
					<p className="mt-1 text-xs text-[var(--text)]">
						{account?.has_password
							? 'A password is stored. Leave this blank to keep it.'
							: 'For Gmail this must be an app password, not your account password.'}
					</p>
				</div>

				<div>
					<label className={labelClass} htmlFor="mail-mailbox">
						Folder
					</label>
					<input
						id="mail-mailbox"
						value={mailbox}
						required
						disabled={saving}
						onChange={(event) => setMailbox(event.target.value)}
						className={`${inputClass} mt-1`}
					/>
				</div>

				<div className="flex flex-wrap items-center gap-2">
					<button
						type="submit"
						disabled={saving || !host.trim() || !username.trim() || needsPassword}
						title={needsPassword ? 'A password is required the first time' : undefined}
						className="cursor-pointer rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
					>
						{saving ? 'Saving…' : 'Save mailbox'}
					</button>

					{storedHere && (
						<button
							type="button"
							onClick={handleClear}
							className="cursor-pointer rounded-md border border-[var(--border)] px-3 py-2 text-sm text-[var(--text)] transition-colors hover:border-red-500 hover:text-red-500"
						>
							Forget it
						</button>
					)}

					{saved && !error && (
						<span className="text-xs text-[var(--text)]">Saved.</span>
					)}
				</div>

				{error && (
					<p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-[var(--text-h)]">
						{error}
					</p>
				)}
			</form>
		</section>
	);
}
