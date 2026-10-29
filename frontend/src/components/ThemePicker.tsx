import { useState } from 'react';

const THEMES = [
	{ value: 'system', label: 'System' },
	{ value: 'light', label: 'Light' },
	{ value: 'dark', label: 'Dark' },
	{ value: 'bauhaus', label: 'Bauhaus' },
] as const;

type Theme = (typeof THEMES)[number]['value'];

const STORAGE_KEY = 'theme';

// index.html reads the same key before first paint.
const ACCENT_KEY = 'accent';

// Only what the picker shows when no custom colour is set; the real default lives in index.css.
const DEFAULT_SWATCH = '#9442d7';

function readAccent(): string | null {
	try {
		const stored = localStorage.getItem(ACCENT_KEY);
		return stored && /^#[0-9a-f]{6}$/i.test(stored) ? stored : null;
	} catch {
		return null;
	}
}

function applyAccent(color: string | null) {
	const root = document.documentElement;
	try {
		if (color === null) localStorage.removeItem(ACCENT_KEY);
		else localStorage.setItem(ACCENT_KEY, color);
	} catch {
		// Storage blocked: same as the theme, it applies until reload.
	}
	if (color === null) root.style.removeProperty('--accent-custom');
	else root.style.setProperty('--accent-custom', color);
}

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
	const [accent, setAccent] = useState<string | null>(readAccent);
	const fixedPalette = theme === 'bauhaus';

	return (
		<>
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

			<section>
				<h3 id="accent-heading" className="font-semibold text-[var(--text-h)]">
					Accent colour
				</h3>
				<p className="mt-1 text-sm text-[var(--text)]">
					{fixedPalette
						? 'Bauhaus keeps its own palette, so this applies to the other themes.'
						: 'Buttons, badges, the active tab and the logo.'}
				</p>
				<div className={`mt-3 flex flex-wrap items-center gap-3 ${fixedPalette ? 'opacity-40' : ''}`}>
					<input
						type="color"
						value={accent ?? DEFAULT_SWATCH}
						onChange={(event) => {
							setAccent(event.target.value);
							applyAccent(event.target.value);
						}}
						aria-labelledby="accent-heading"
						className="h-10 w-16 cursor-pointer border-[3px] border-[var(--frame)] bg-transparent p-0 [&::-moz-color-swatch]:border-none [&::-webkit-color-swatch]:border-none [&::-webkit-color-swatch-wrapper]:p-0"
					/>
					<span className="font-mono text-sm text-[var(--text-h)] uppercase">
						{accent ?? 'Default'}
					</span>
					{accent !== null && (
						<button
							type="button"
							onClick={() => {
								setAccent(null);
								applyAccent(null);
							}}
							className="cursor-pointer border-[3px] border-[var(--frame)] px-3 py-1 text-sm text-[var(--text)] transition-colors hover:text-[var(--text-h)]"
						>
							Reset
						</button>
					)}
				</div>
			</section>
		</>
	);
}
