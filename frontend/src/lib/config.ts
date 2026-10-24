/**
 * Configuration du frontend, lue depuis les variables `NEXT_PUBLIC_*`.
 *
 * Ces variables sont FIGÉES AU BUILD (build args du Dockerfile, cf.
 * docker-compose.yml) : Next.js les remplace dans le bundle au moment du
 * `next build`. Elles doivent donc être lues de façon statique
 * (`process.env.NEXT_PUBLIC_X`), jamais via un index dynamique.
 */

/** Base des appels REST vers le backend FastAPI. */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

/** URL du WebSocket temps réel du backend. */
export const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000").replace(
  /\/+$/,
  "",
);

/** Nom affiché dans l'en-tête de l'application. */
export const PARKING_NAME = process.env.NEXT_PUBLIC_PARKING_NAME ?? "SM-Park";
