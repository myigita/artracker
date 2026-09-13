import type { MatchField, MatchOperator, MatchRuleIn } from '../api';

type Props = {
	rules: MatchRuleIn[];
	onChange: (rules: MatchRuleIn[]) => void;
	disabled?: boolean;
	valueHint?: string;
};

// Controlled rather than self-saving: rules are edited inside the tracker's edit
// form and go up with everything else on Save, so a half-typed rule can be
// abandoned by cancelling — the same as a half-typed URL.

const FIELDS: { value: MatchField; label: string }[] = [
	{ value: 'sender', label: 'Sender' },
	{ value: 'subject', label: 'Subject' },
];

const OPERATORS: { value: MatchOperator; label: string }[] = [
	{ value: 'contains', label: 'contains' },
	{ value: 'not_contains', label: "doesn't contain" },
	{ value: 'equals', label: 'is exactly' },
	{ value: 'not_equals', label: 'is not' },
];

const selectClass =
	'shrink-0 rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs ' +
	'text-[var(--text-h)] outline-none transition-colors focus:border-[var(--accent-border)] ' +
	'disabled:opacity-40';

export default function MatchRulesEditor({ rules, onChange, disabled, valueHint }: Props) {
	function update(index: number, patch: Partial<MatchRuleIn>) {
		onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
	}

	function remove(index: number) {
		onChange(rules.filter((_, i) => i !== index));
	}

	function add() {
		onChange([...rules, { field: 'sender', operator: 'contains', value: '' }]);
	}

	return (
		<div>
			<div className="flex items-baseline gap-2">
				<span className="text-xs font-medium text-[var(--text)]">Match rules</span>
				<span className="text-xs text-[var(--text)]">
					Mail has to satisfy every rule, including one positive match.
				</span>
			</div>

			<div className="mt-2 flex flex-col gap-2">
				{rules.map((rule, index) => (
					// Index as key, deliberately. These rows have no stable identity —
					// the server replaces the whole set on save and assigns new ids — and
					// reordering isn't possible, so the index IS the identity here.
					<div key={index} className="flex flex-wrap items-center gap-2">
						<select
							value={rule.field}
							disabled={disabled}
							onChange={(e) => update(index, { field: e.target.value as MatchField })}
							aria-label={`Rule ${index + 1} field`}
							className={selectClass}
						>
							{FIELDS.map((f) => (
								<option key={f.value} value={f.value}>
									{f.label}
								</option>
							))}
						</select>

						<select
							value={rule.operator}
							disabled={disabled}
							onChange={(e) =>
								update(index, { operator: e.target.value as MatchOperator })
							}
							aria-label={`Rule ${index + 1} operator`}
							className={selectClass}
						>
							{OPERATORS.map((o) => (
								<option key={o.value} value={o.value}>
									{o.label}
								</option>
							))}
						</select>

						<input
							value={rule.value}
							disabled={disabled}
							onChange={(e) => update(index, { value: e.target.value })}
							placeholder={valueHint || (rule.field === 'sender' ? 'artist handle' : 'artist name')}
							aria-label={`Rule ${index + 1} value`}
							className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs text-[var(--text-h)] outline-none transition-colors focus:border-[var(--accent-border)] disabled:opacity-40"
						/>

						<button
							type="button"
							onClick={() => remove(index)}
							disabled={disabled}
							aria-label={`Remove rule ${index + 1}`}
							className="shrink-0 cursor-pointer p-1 text-[var(--text)] transition-colors hover:text-red-500 focus-visible:text-red-500 disabled:opacity-40"
						>
							<svg
								width="14"
								height="14"
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
				))}

				<div>
					<button
						type="button"
						onClick={add}
						disabled={disabled}
						className="cursor-pointer rounded-md border border-dashed border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text)] transition-colors hover:border-[var(--accent-border)] hover:text-[var(--text-h)] disabled:opacity-40"
					>
						+ Add rule
					</button>
				</div>
			</div>

			{rules.length === 0 && (
				<p className="mt-2 text-xs text-[var(--text)]">
					No rules, so no mail will ever match this tracker.
				</p>
			)}
		</div>
	);
}
