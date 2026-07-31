/** Backend location and response types, shared by the server and client fetches. */

/**
 * Only NEXT_PUBLIC_* variables reach the browser bundle -- correct for a URL
 * the browser must know, never for a secret. Inlined at build time, so
 * changing it in Vercel requires a redeploy.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Mirrors HealthResponse in backend/app/main.py; also published at /openapi.json. */
export type HealthResponse = {
  status: "ok" | "degraded";
  environment: string;
  database: string;
  database_time: string | null;
};
