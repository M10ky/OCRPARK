import { API_BASE_URL } from "./config";
import type {
  BarrierStatus,
  SlotsSummary,
  Token,
  User,
  Visit,
} from "./types";

/** Erreur d'API : porte le code HTTP et le message lisible du backend. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/**
 * Enregistre le callback invoqué quand le backend répond 401.
 * L'AuthProvider l'utilise pour purger la session et renvoyer vers /login.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  token?: string | null;
  /** Corps JSON. */
  json?: unknown;
  /** Corps `application/x-www-form-urlencoded` (login). */
  form?: Record<string, string>;
  /** Corps multipart (upload de fichier). */
  multipart?: FormData;
  /**
   * `true` si un 401 est une erreur de formulaire (login) et non une
   * session expirée : dans ce cas le handler global n'est pas appelé.
   */
  skipUnauthorized?: boolean;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** Extrait le message d'erreur d'une réponse FastAPI (`{ "detail": ... }`). */
function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return first.msg;
  }
  return null;
}

/**
 * Wrapper HTTP unique du frontend.
 *
 * - joint le token JWT (`Authorization: Bearer`) ;
 * - distingue les 3 modes de corps (JSON / form-urlencoded / multipart) ;
 * - signale les 401 via le handler global (session expirée) ;
 * - traduit les erreurs FastAPI en messages lisibles.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", token, json, form, multipart, skipUnauthorized } = options;

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (multipart) {
    body = multipart;
  } else if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(form).toString();
  } else if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      0,
      "Backend injoignable. Vérifiez que le conteneur backend est démarré et que NEXT_PUBLIC_BACKEND_URL est correct.",
    );
  }

  if (response.status === 401) {
    if (!skipUnauthorized) unauthorizedHandler?.();
    throw new ApiError(401, "Identifiants incorrects ou session expirée.");
  }
  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload: unknown = text ? safeParse(text) : null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      extractDetail(payload) ?? `Erreur HTTP ${response.status}.`,
    );
  }
  return payload as T;
}

/** Endpoints consommés par le frontend (un par route métier du backend). */
export const api = {
  /** `POST /api/auth/login` — attend un formulaire OAuth2, pas du JSON. */
  login: (username: string, password: string) =>
    request<Token>("/api/auth/login", {
      method: "POST",
      form: { username, password },
      skipUnauthorized: true,
    }),

  /** `GET /api/auth/me` — profil de l'utilisateur authentifié. */
  me: (token: string) => request<User>("/api/auth/me", { token }),

  /** `GET /api/slots` — occupation des places (état initial, avant le WS). */
  slots: (token: string) => request<SlotsSummary>("/api/slots", { token }),

  /** `GET /api/visits/current` — véhicules actuellement dans le parking. */
  currentVisits: (token: string) => request<Visit[]>("/api/visits/current", { token }),

  /** `GET /api/barrier/state` — état de la barrière + dernière commande. */
  barrierStatus: (token: string) => request<BarrierStatus>("/api/barrier/state", { token }),
};
