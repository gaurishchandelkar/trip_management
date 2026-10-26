import type { InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  /** The rule for the field, shown before the member fails it. */
  hint?: string;
  invalid?: boolean;
}

export function Field({ id, label, hint, invalid = false, className, ...input }: FieldProps) {
  const hintId = hint === undefined ? undefined : `${id}-hint`;
  return (
    <div className={["field", className].filter(Boolean).join(" ")}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="field__input"
        aria-describedby={hintId}
        aria-invalid={invalid || undefined}
        {...input}
      />
      {hint !== undefined && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
    </div>
  );
}
