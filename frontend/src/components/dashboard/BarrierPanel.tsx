import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { BarrierState } from "@/lib/types";

interface BarrierPanelProps {
  barrier: BarrierState | null;
}

const STATE_LABELS: Record<string, string> = {
  online: "En ligne",
  offline: "Hors ligne",
  idle: "En attente",
  opening: "Ouverture",
  open: "Ouverte",
  closing: "Fermeture",
  closed: "Fermée",
};

function stateTone(state: string | null): "ok" | "warn" | "danger" | "neutral" {
  if (!state) return "neutral";
  if (state === "offline") return "danger";
  if (state === "online" || state === "open" || state === "closed") return "ok";
  return "warn";
}

function ackTone(ack: string | null): "ok" | "warn" | "danger" | "neutral" {
  if (ack === "acknowledged") return "ok";
  if (ack === "timeout") return "danger";
  if (ack === "pending") return "warn";
  // null = heartbeat sans correlation_id (ce n'est PAS un ACK).
  return "neutral";
}

function ackLabel(ack: string | null): string {
  if (ack === "acknowledged") return "ACK reçu";
  if (ack === "timeout") return "ACK expiré";
  if (ack === "pending") return "ACK en attente";
  return "Aucun ACK (heartbeat)";
}

/** Panneau d'état de la barrière (porte + état + statut d'accusé de réception). */
export function BarrierPanel({ barrier }: BarrierPanelProps) {
  const state = barrier?.state ?? null;
  const gate = barrier?.gate ?? null;

  return (
    <Card title="Barrière" description="État publié par le firmware ESP32">
      <dl className="grid gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-foreground/60">État</dt>
          <dd className="mt-1">
            <Badge tone={stateTone(state)}>{STATE_LABELS[state ?? ""] ?? state ?? "—"}</Badge>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-foreground/60">Porte</dt>
          <dd className="mt-1 text-sm font-medium">
            {gate === "entry" ? "Entrée" : gate === "exit" ? "Sortie" : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-foreground/60">Accusé</dt>
          <dd className="mt-1">
            <Badge tone={ackTone(barrier?.ack_status ?? null)}>
              {ackLabel(barrier?.ack_status ?? null)}
            </Badge>
          </dd>
        </div>
      </dl>

      {barrier?.reason && (
        <p className="mt-3 text-xs text-foreground/50">Motif : {barrier.reason}</p>
      )}
      {barrier?.correlation_id && (
        <p className="mt-1 truncate text-xs text-foreground/50">
          correlation_id : {barrier.correlation_id}
        </p>
      )}
    </Card>
  );
}
