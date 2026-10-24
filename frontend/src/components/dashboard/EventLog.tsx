import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { LiveEntry } from "@/components/providers/LiveProvider";

interface EventLogProps {
  entries: LiveEntry[];
}

const TONE_CLASS: Record<LiveEntry["tone"], string> = {
  neutral: "border-border",
  ok: "border-ok/40",
  warn: "border-warn/40",
  danger: "border-danger/40",
};

function formatTime(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleTimeString("fr-FR", { hour12: false });
}

/** Journal des événements temps réels (100 derniers). */
export function EventLog({ entries }: EventLogProps) {
  return (
    <Card title="Journal temps réel" description="Événements reçus du backend">
      {entries.length === 0 ? (
        <p className="text-sm text-foreground/50">
          Aucun événement reçu pour le moment.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className={`flex items-start gap-3 rounded-lg border-l-2 bg-surface-2/60 px-3 py-2 ${TONE_CLASS[entry.tone]}`}
            >
              <span className="font-mono text-xs text-foreground/50">
                {formatTime(entry.ts)}
              </span>
              <span className="flex-1 text-sm">{entry.message}</span>
              <Badge tone="neutral">{entry.type}</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
