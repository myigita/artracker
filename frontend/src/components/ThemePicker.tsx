import { useState } from 'react';

const THEMES = [
	{ value: 'system', label: 'System' },
	{ value: 'light', label: 'Light' },
	{ value: 'dark', label: 'Dark' },
	{ value: 'bauhaus', label: 'Bauhaus' },
] as const;

type Theme = (typeof THEMES)[number]['value'];

const STORAGE_KEY = 'theme';

function readTheme(): Theme {
	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		return THEMES.some((t) => t.value === stored) ? (stored as Theme) : 'system';
	} catch {
		return 'system';
	}
}

function applyTheme(theme: Theme) {
	const root = document.documentElement;
	try {
		if (theme === 'system') localStorage.removeItem(STORAGE_KEY);
		else localStorage.setItem(STORAGE_KEY, theme);
	} catch {
		// Storage blocked: the choice still applies, it just won't survive a reload.
	}
	if (theme === 'system') delete root.dataset.theme;
	else root.dataset.theme = theme;
}

export default function ThemePicker() {
	const [theme, setTheme] = useState<Theme>(readTheme);

	return (
		<section>
			<h3 id="theme-heading" className="font-semibold text-[var(--text-h)]">
				Theme
			</h3>
			<div role="radiogroup" aria-labelledby="theme-heading" className="mt-3 flex flex-col gap-2">
				{THEMES.map(({ value, label }) => (
					<label
						key={value}
						className="flex cursor-pointer items-center gap-2 text-sm text-[var(--text-h)]"
					>
						<input
							type="radio"
							name="theme"
							checked={theme === value}
							onChange={() => {
								setTheme(value);
								applyTheme(value);
							}}
							className="cursor-pointer accent-[var(--accent)]"
						/>
						{label}
					</label>
				))}
			</div>
		</section>
	);
}
