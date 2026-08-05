/**
 * Home page -- a Server Component (the App Router default).
 *
 * Runs in Node, so it can await directly in the render body and the data is
 * embedded in the HTML. Being server-side, this fetch is not subject to CORS.
 */

import Link from "next/link";

import LiveHealth from "@/components/live-health";
import { API_BASE_URL, type HealthResponse } from "@/lib/api";

export default async function Home() {
  let health: HealthResponse | null = null;
  let error: string | null = null;

  try {
    // Never cache a health check.
    const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    health = await res.json();
  } catch (e) {
    // A down backend is an expected state, not a crash -- keep the page up.
    error = e instanceof Error ? e.message : "unknown error";
  }

  const ok = health?.status === "ok";

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 p-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">E-Commerce AI</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Phase 1 &mdash; proving the stack end to end.
        </p>
        <Link
          href="/products"
          className="mt-4 inline-block rounded-md border border-zinc-300 px-4 py-2 text-sm transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Browse the catalog &rarr;
        </Link>
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
              Is the API reachable at {API_BASE_URL}?
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

      <LiveHealth />

      <p className="text-xs leading-relaxed text-zinc-500">
        The panel above was rendered on the server &mdash; the timestamp is in
        the HTML source and survives with JavaScript disabled.
      </p>
    </main>
  );
}
