/**
 * Home page -- a SERVER COMPONENT.
 *
 * In the App Router every component is a Server Component unless it opts out
 * with the "use client" directive. This one runs in Node on the server, never
 * in the browser. Two consequences:
 *
 *   1. It can be `async` and `await` right in the render body. There is no
 *      useEffect, no useState, no loading flag -- the HTML is sent to the
 *      browser with the data already baked in.
 *
 *   2. The fetch below is a server-to-server call. No browser is involved, so
 *      the same-origin policy never applies and CORS is irrelevant here.
 *      Remember that when the client-side version of this fails.
 */

import LiveHealth from "@/components/live-health";

// The API's address. This will move into an environment variable when we
// deploy -- localhost means nothing to a server running in Oregon. Hardcoded
// for now so there is exactly one new concept in this file.
const API_BASE_URL = "http://127.0.0.1:8000";

// Mirrors the Pydantic HealthResponse in backend/app/main.py. The same
// contract, written twice in two languages: TypeScript cannot check what
// arrives over a network, so if the backend changes and this does not, you get
// `undefined` at runtime rather than a compile error. (FastAPI publishes this
// shape at /openapi.json, so it can be generated later instead of hand-written.)
type HealthResponse = {
  status: "ok" | "degraded";
  environment: string;
  database: string;
  database_time: string | null;
};

export default async function Home() {
  let health: HealthResponse | null = null;
  let error: string | null = null;

  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      // Never serve a health check from cache -- a cached "ok" from ten
      // minutes ago says nothing about right now. Next.js 16 does not cache
      // fetch by default, but being explicit documents the intent and survives
      // someone later turning on Cache Components.
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    health = await res.json();
  } catch (e) {
    // The backend being down is a normal condition, not a crash. Catching it
    // means the page still renders and tells you what is wrong, instead of
    // showing Next.js's error overlay.
    error = e instanceof Error ? e.message : "unknown error";
  }

  const ok = health?.status === "ok";

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 p-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          E-Commerce AI
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Phase 1 &mdash; proving the stack end to end.
        </p>
      </div>

      <section className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              ok ? "bg-green-500" : "bg-red-500"
            }`}
            aria-hidden
          />
          <h2 className="font-medium">
            Backend {ok ? "healthy" : "unreachable"}
          </h2>
        </div>

        {error ? (
          <div className="mt-4 text-sm">
            <p className="text-red-600 dark:text-red-400">{error}</p>
            <p className="mt-2 text-zinc-500">
              Is uvicorn running on {API_BASE_URL}?
            </p>
          </div>
        ) : (
          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-zinc-500">Status</dt>
            <dd className="font-mono">{health?.status}</dd>

            <dt className="text-zinc-500">Environment</dt>
            <dd className="font-mono">{health?.environment}</dd>

            <dt className="text-zinc-500">Database</dt>
            <dd className="font-mono">{health?.database}</dd>

            <dt className="text-zinc-500">Postgres clock</dt>
            <dd className="font-mono">{health?.database_time}</dd>
          </dl>
        )}
      </section>

      {/* A Server Component rendering a Client Component. The server renders
          a placeholder plus a reference to this component's JavaScript; the
          browser downloads that JS and takes over from there. */}
      <LiveHealth />

      <p className="text-xs leading-relaxed text-zinc-500">
        This data was fetched on the <strong>server</strong> and embedded in the
        HTML before it reached your browser. Disable JavaScript and reload
        &mdash; it still works. View source and you will find the Postgres
        timestamp already in the markup.
      </p>
    </main>
  );
}
