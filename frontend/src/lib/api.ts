/**
 * Where the backend lives, and what it returns.
 *
 * Extracted here now that two components need it. Before that there was one
 * caller and a shared module would have been guesswork; now the alternative is
 * changing the same URL in two files and forgetting one.
 */

/**
 * The NEXT_PUBLIC_ prefix is a security boundary, not a naming style.
 *
 * Next.js inlines ONLY variables prefixed with NEXT_PUBLIC_ into the
 * JavaScript bundle it ships to the browser. Anything else is replaced with an
 * empty string on the client, so a secret cannot leak by accident.
 *
 * An API base URL must be public -- the browser has to know where to send
 * requests, and anyone can read it in DevTools regardless. So the prefix is
 * correct here. A database password or JWT signing key must never have it.
 *
 * The localhost fallback keeps `npm run dev` working with no setup. In
 * production Vercel supplies the real value, and if it is ever missing the
 * page will visibly try to reach localhost and fail -- which is a much louder
 * failure than silently rendering nothing.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Mirrors the Pydantic `HealthResponse` in backend/app/main.py.
 *
 * The same contract expressed twice in two languages. TypeScript cannot verify
 * what actually arrives over a network, so if the backend changes and this
 * does not, you get `undefined` at runtime rather than a compile error.
 * FastAPI publishes this shape at /openapi.json, so it can be code-generated
 * later instead of hand-maintained.
 */
export type HealthResponse = {
  status: "ok" | "degraded";
  environment: string;
  database: string;
  database_time: string | null;
};
