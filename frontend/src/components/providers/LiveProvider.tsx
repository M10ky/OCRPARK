"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { WS_URL } from "@/lib/config";
import type {
  BarrierState,
  Slot,
  Visit,
  WsEvent,
  WsEventType,
} from "@/lib/types";

export type LiveStatus = "idle" | "connecting" | "open" | "reconnecting";

/** Entrée du journal temps réel (déjà traduite en français). */
export interface LiveEntry {
  id: string;
  type: WsEventType;
  ts: string;
  tone: "neutral" | "ok" | "warn" | "danger";
  message: string;
}

export interface LiveState {
  status: LiveStatus;
  slots: Slot[];
  visits: Visit[];
  barrier: BarrierState | null;
  entries: LiveEntry[];
  lastEventTs: string | null;
}

export interface LiveContextValue extends LiveState {
  /** Force une reconnexion immédiate (utile après une perte réseau). */
  reconnect: () => void;
}

const LiveContext = createContext<LiveContextValue | null>(null);

/** Exporté pour `useLive()` (le hook est le point d'entrée public). */
export { LiveContext };

const MAX_ENTRIES = 100;
const PING_INTERVAL_MS = 25_000;
const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 10_000;

/** Traduit un événement WS en ligne de journal lisible. */
function describe(event: WsEvent): { tone: LiveEntry["tone"]; message: string } | null {
  const payload = event.payload as Record<string, unknown>;

  switch (event.type) {
    case "slots": {
      const slots = (payload?.slots as Slot[]) ?? [];
      const occupied = slots.filter((slot) => slot.occupied).length;
      return {
        tone: "neutral",
        message: `Occupation : ${occupied}/${slots.length} place(s) occupée(s)`,
      };
    }
    case "visit": {
      const visit = payload as unknown as Visit;
      const plate = visit?.plate ?? "plaque inconnue";
      const entering = visit?.exit_at === null || visit?.exit_at === undefined;
      return {
        tone: entering ? "ok" : "neutral",
        message: entering ? `Entrée — ${plate}` : `Sortie — ${plate}`,
      };
    }
    case "passage": {
      const passage = payload as Record<string, unknown>;
      const plate = (passage?.plate as string) ?? "plaque inconnue";
      const allowed = passage?.allowed === true;
      const action = (passage?.action as string) ?? "aucune action";
      return {
        tone: allowed ? "ok" : "danger",
        message: `${plate} — ${allowed ? "autorisé" : "refusé"} (${action})`,
      };
    }
    case "barrier": {
      const barrier = payload as unknown as BarrierState;
      const gate = barrier?.gate ?? "?";
      const state = barrier?.state ?? "inconnue";
      const ack = barrier?.ack_status;
      const ackLabel = ack === "acknowledged" ? "ACK" : ack ? `ACK:${ack}` : "";
      return {
        tone: ack === "timeout" ? "danger" : "neutral",
        message: `Barrière ${gate} — ${state}${ackLabel ? ` (${ackLabel})` : ""}`,
      };
    }
    case "mqtt": {
      const topic = (payload?.topic as string) ?? "?";
      return { tone: "warn", message: `MQTT ${topic}` };
    }
    default:
      return null;
  }
}

/**
 * Source de vérité temps réel du frontend.
 *
 * - UN SEUL WebSocket pour toute l'application (`/ws/events`).
 * - Reconnexion automatique avec backoff exponentiel (1 s → 10 s).
 * - Code de fermeture `4401` ⇒ session expirée ⇒ déconnexion.
 * - Ping périodique : le backend attend `receive_text()`, sans ping il ne
 *   détecterait pas la disparition d'un client.
 */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { token, status: authStatus, logout } = useAuth();

  const [status, setStatus] = useState<LiveStatus>("idle");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [barrier, setBarrier] = useState<BarrierState | null>(null);
  const [entries, setEntries] = useState<LiveEntry[]>([]);
  const [lastEventTs, setLastEventTs] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptRef = useRef(0);
  const closedByUsRef = useRef(false);
  const entrySeqRef = useRef(0);

  const pushEntry = useCallback((entry: Omit<LiveEntry, "id">) => {
    entrySeqRef.current += 1;
    const id = `${Date.now()}-${entrySeqRef.current}`;
    setEntries((previous) => [{ ...entry, id }, ...previous].slice(0, MAX_ENTRIES));
  }, []);

  const applyEvent = useCallback(
    (event: WsEvent) => {
      setLastEventTs(event.ts ?? null);

      if (event.type === "snapshot") {
        const snapshot = event.payload as {
          slots?: { slots?: Slot[] };
          visits?: Visit[];
          barrier?: BarrierState | null;
        };
        setSlots(snapshot?.slots?.slots ?? []);
        setVisits(snapshot?.visits ?? []);
        setBarrier(snapshot?.barrier ?? null);
        return;
      }

      if (event.type === "slots") {
        const payload = event.payload as { slots?: Slot[] } | Slot[];
        const list = Array.isArray(payload) ? payload : (payload?.slots ?? []);
        setSlots(list);
      } else if (event.type === "visit") {
        const visit = event.payload as unknown as Visit;
        setVisits((previous) => {
          const index = previous.findIndex((item) => item.id === visit.id);
          if (index === -1) return [visit, ...previous];
          const next = [...previous];
          next[index] = visit;
          return next;
        });
      } else if (event.type === "barrier") {
        setBarrier(event.payload as unknown as BarrierState);
      }

      const described = describe(event);
      if (described) {
        pushEntry({
          type: event.type,
          ts: event.ts ?? new Date().toISOString(),
          tone: described.tone,
          message: described.message,
        });
      }
    },
    [pushEntry],
  );

  // État initial par REST : le dashboard est utilisable même si le WS tarde.
  useEffect(() => {
    if (authStatus !== "authenticated" || !token) return;
    let cancelled = false;

    api
      .slots(token)
      .then((summary) => {
        if (!cancelled) setSlots(summary.slots ?? []);
      })
      .catch(() => undefined);

    api
      .currentVisits(token)
      .then((list) => {
        if (!cancelled) setVisits(list ?? []);
      })
      .catch(() => undefined);

    api
      .barrierStatus(token)
      .then((status_) => {
        if (!cancelled) setBarrier(status_?.state ?? null);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [authStatus, token]);

  // Connexion WebSocket + reconnexion.
  useEffect(() => {
    if (authStatus !== "authenticated" || !token) {
      socketRef.current?.close();
      socketRef.current = null;
      setStatus("idle");
      return;
    }

    closedByUsRef.current = false;

    const clearTimers = () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      reconnectTimerRef.current = null;
      pingTimerRef.current = null;
    };

    const connect = () => {
      setStatus(attemptRef.current === 0 ? "connecting" : "reconnecting");

      const url = token
        ? `${WS_URL}/ws/events?token=${encodeURIComponent(token)}`
        : `${WS_URL}/ws/events`;

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        attemptRef.current = 0;
        setStatus("open");
        pingTimerRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send("ping");
        }, PING_INTERVAL_MS);
      };

      socket.onmessage = (message: MessageEvent<string>) => {
        try {
          const event = JSON.parse(message.data) as WsEvent;
          if (event && typeof event.type === "string") applyEvent(event);
        } catch {
          // Message illisible : ignoré (le contrat garantit du JSON).
        }
      };

      socket.onerror = () => {
        // La fermeture suit toujours ; rien à faire ici.
      };

      socket.onclose = (event: CloseEvent) => {
        if (pingTimerRef.current) clearInterval(pingTimerRef.current);
        pingTimerRef.current = null;
        socketRef.current = null;

        if (event.code === 4401) {
          // Session expirée : on purge la session locale (RequireAuth
          // redirigera ensuite vers /login).
          setStatus("idle");
          logout();
          return;
        }
        if (!closedByUsRef.current) scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      attemptRef.current += 1;
      const delay = Math.min(
        BACKOFF_BASE_MS * 2 ** (attemptRef.current - 1),
        BACKOFF_MAX_MS,
      );
      setStatus("reconnecting");
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    connect();

    return () => {
      closedByUsRef.current = true;
      clearTimers();
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [applyEvent, authStatus, logout, token]);

  const reconnect = useCallback(() => {
    socketRef.current?.close();
  }, []);

  const value = useMemo<LiveContextValue>(
    () => ({ status, slots, visits, barrier, entries, lastEventTs, reconnect }),
    [status, slots, visits, barrier, entries, lastEventTs, reconnect],
  );

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}
