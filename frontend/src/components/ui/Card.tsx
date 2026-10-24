import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Panneau de contenu : l'unité de mise en page de base de l'application. */
export function Card({ title, description, action, children, className = "" }: CardProps) {
  return (
    <section
      className={`rounded-xl border border-border bg-surface shadow-sm ${className}`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            {title && <h2 className="text-base font-semibold text-foreground">{title}</h2>}
            {description && <p className="mt-1 text-sm text-foreground/60">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}
