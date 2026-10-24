import { Card } from "@/components/ui/Card";
import type { Slot } from "@/lib/types";

interface SlotGridProps {
  slots: Slot[];
}

/**
 * Jauges d'occupation des places.
 *
 * ⚠️ Les places proviennent de deux sources de formes différentes :
 * - REST (`GET /api/slots`) : `{ id, label, occupied, updated_at }`
 * - WebSocket (`slots`)      : `{ id, occupied }`
 * `label` est donc optionnel : on affiche un repli `Place N`.
 */
export function SlotGrid({ slots }: SlotGridProps) {
  if (slots.length === 0) {
    return (
      <Card title="Occupation des places">
        <p className="text-sm text-foreground/50">
          Aucune place connue. Vérifiez que le firmware publie bien sur
          <code className="mx-1 rounded bg-surface-2 px-1">parking/state</code>.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Occupation des places" description="Mises à jour en temps réel">
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {slots.map((slot) => (
          <li
            key={slot.id}
            className={`rounded-lg border p-3 transition-colors ${
              slot.occupied
                ? "border-danger/30 bg-danger/5"
                : "border-ok/30 bg-ok/5"
            }`}
          >
            <p className="text-xs font-medium text-foreground/60">
              {slot.label ?? `Place ${slot.id}`}
            </p>
            <p className="mt-1 text-sm font-semibold">
              {slot.occupied ? "Occupée" : "Libre"}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}
