import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | null;
  hint?: string;
}

/** Champ de formulaire : libellé, saisie, message d'erreur et aide. */
export function Input({ label, error, hint, id, className = "", ...rest }: InputProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-foreground/80">
        {label}
      </label>
      <input
        id={inputId}
        className={`rounded-lg border bg-surface px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-foreground/40 focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:opacity-60 ${error ? "border-danger" : "border-border"} ${className}`}
        {...rest}
      />
      {hint && !error && <p className="text-xs text-foreground/50">{hint}</p>}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
