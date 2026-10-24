"use client";

import { BarrierPanel } from "@/components/dashboard/BarrierPanel";
import { EventLog } from "@/components/dashboard/EventLog";
import { SlotGrid } from "@/components/dashboard/SlotGrid";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { useLive } from "@/hooks/useLive";
import type { Visit } from "@/lib/types";

function Kpi({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-foreground/50">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-foreground/50">{hint}</p>}
    </div>
  );
}

function plateOf(visit: Visit): string {
  return visit.plate ?? "plaque inconnue";
}

/** Dashboard temps réel : occupation, barrière, véhicules présents, journal. */
export default function DashboardPage() {
  const { status, slots, visits, barrier, entries, lastEventTs } = useLive();

  const occupied = slots.filter((slot) => slot.occupied).length;
  const free = Math.max(slots.length - occupied, 0);

  const statusBadge =
    status === "open"
      ? { tone: "ok" as const, label: "Temps réel" }
      : status === "connecting"
        ? { tone: "warn" as const, label: "Connexion…" }
        : status === "reconnecting"
          ? { tone: "warn" as const, label: "Reconnexion…" }
          : { tone: "neutral" as const, label: "Hors ligne" };

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-foreground/60">
            Occupation du parking et état de la barrière en temps réel.
          </p>
        </div>
        <Badge tone={statusBadge.tone}>{statusBadge.label}</Badge>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Places" value={slots.length} />
        <Kpi label="Occupées" value={occupied} />
        <Kpi label="Libres" value={free} />
        <Kpi
          label="Véhicules présents"
          value={visits.length}
          hint={lastEventTs ? `dernier événement ${new Date(lastEventTs).toLocaleTimeString("fr-FR", { hour12: false })}` : undefined}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <SlotGrid slots={slots} />
        <BarrierPanel barrier={barrier} />
      </section>

      {visits.length > 0 && (
        <Card title="Véhicules dans le parking">
          <ul className="flex flex-col gap-2">
            {visits.map((visit) => (
              <li
                key={visit.id}
                className="flex items-center justify-between rounded-lg bg-surface-2/60 px-3 py-2 text-sm"
              >
                <span className="font-medium">{plateOf(visit)}</span>
                <span className="text-xs text-foreground/50">
                  entrée {new Date(visit.entry_at).toLocaleTimeString("fr-FR", { hour12: false })}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <EventLog entries={entries} />
    </div>
  );
}
