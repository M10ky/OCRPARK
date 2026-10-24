/**
 * Types TypeScript alignés sur les schémas Pydantic du backend.
 *
 * Source : `backend/app/schemas/*.py` et `docs/websocket-contract.md`.
 * Toute modification du backend doit être répercutée ici.
 */

// --- Authentification ------------------------------------------------------

export interface Token {
  access_token: string;
  token_type: string;
}

export interface User {
  username: string;
  email: string | null;
  is_active: boolean;
  is_admin: boolean;
}

// --- Occupation des places -------------------------------------------------

/**
 * ⚠️ TRAP 1 : `GET /api/slots` renvoie `{ id, label, occupied, updated_at }`
 * mais l'événement WebSocket `slots` renvoie `{ id, occupied }` uniquement.
 * `label` et `updated_at` sont donc OPTIONNELS.
 */
export interface Slot {
  id: number;
  occupied: boolean;
  label?: string | null;
  updated_at?: string;
}

export interface SlotsSummary {
  slots: Slot[];
  total: number;
  occupied: number;
  free: number;
}

// --- Barrière --------------------------------------------------------------

export type BarrierStateName =
  | "online"
  | "offline"
  | "idle"
  | "opening"
  | "open"
  | "closing"
  | "closed";

/**
 * ⚠️ TRAP 2 : `ack_status` vaut `null` quand le message MQTT ne portait pas
 * de `correlation_id` (heartbeat) — ce n'est PAS un ACK.
 */
export type AckStatus = "pending" | "acknowledged" | "timeout";

export interface BarrierState {
  state: BarrierStateName | null;
  gate: "entry" | "exit" | null;
  reason: string | null;
  correlation_id: string | null;
  ack_status: AckStatus | null;
  ts: string | null;
}

export interface BarrierCommand {
  correlation_id: string;
  passage_id: string | null;
  action: string;
  gate: string;
  status: "pending" | "acknowledged" | "timeout";
  created_at: string;
  acked_at: string | null;
}

export interface BarrierStatus {
  state: BarrierState | null;
  last_command: BarrierCommand | null;
}

// --- Visites et passages ---------------------------------------------------

export interface Visit {
  id: string;
  plate: string | null;
  entry_gate: string;
  exit_gate: string | null;
  status: "inside" | "closed";
  entry_at: string;
  exit_at: string | null;
  entry_passage_id: string | null;
  exit_passage_id: string | null;
}

export interface Passage {
  id: string;
  plate: string | null;
  recognized: boolean;
  confidence: number | null;
  allowed: boolean;
  source: string | null;
  action: string | null;
  barrier_command_sent: boolean;
  barrier_action: string | null;
  mqtt_topic: string | null;
  reason: string | null;
  ocr_detections: unknown;
  raw_image_ref: string | null;
  created_at: string;
}

export interface PassageStats {
  total: number;
  authorized: number;
  denied: number;
  recognized: number;
  unrecognized: number;
}

// --- Plaques autorisées ----------------------------------------------------

export interface AllowedPlate {
  id: string;
  plate: string;
  description: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// --- Décision d'orchestration ---------------------------------------------

export interface OrchestrateResult {
  plate: string | null;
  recognized: boolean;
  confidence: number | null;
  authorized: boolean;
  allowed: boolean;
  action: string | null;
  gate: string;
  barrier_command_sent: boolean;
  barrier_action: string | null;
  barrier_ack_status: AckStatus | null;
  total_slots: number | null;
  free_slots: number | null;
  reason: string | null;
  source: string;
  correlation_id: string | null;
  detections: unknown;
}

// --- WebSocket -------------------------------------------------------------

export type WsEventType = "snapshot" | "slots" | "visit" | "passage" | "barrier" | "mqtt";

export interface WsEvent<T = unknown> {
  type: WsEventType;
  payload: T;
  ts: string;
}

export interface SnapshotPayload {
  slots: SlotsSummary;
  visits: Visit[];
  barrier: BarrierState | null;
}
