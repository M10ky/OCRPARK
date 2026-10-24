import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "brand" | "ok" | "warn" | "danger";

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-foreground/70 border-border",
  brand: "bg-brand/10 text-brand border-brand/30",
  ok: "bg-ok/10 text-ok border-ok/30",
  warn: "bg-warn/10 text-warn border-warn/30",
  danger: "bg-danger/10 text-danger border-danger/30",
};

/** Pastille de statut (place libre/occupée, ACK, parking plein...). */
export function Badge({ tone = "neutral", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
