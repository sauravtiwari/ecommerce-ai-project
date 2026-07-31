"use client";

/**
 * The same /health request as page.tsx, but issued by the browser.
 *
 * "use client" ships this file to the browser and runs it there, which enables
 * hooks and event handlers -- and makes the fetch subject to CORS.
 */

import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL, type HealthResponse } from "@/lib/api";

export default function LiveHealth() {
  // Client-side fetching must render before data exists, so every in-between
  // state needs representing -- none of which the server version required.
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      // A CORS failure yields only "Failed to fetch" here; the real reason is
      // in the DevTools console, never in this catch block.
      setError(e instanceof Error ? e.message : "unknown error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const ok = data?.status === "ok";

  return (
    <section className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              loading ? "bg-amber-400" : ok ? "bg-green-500" : "bg-red-500"
            }`}
            aria-hidden
          />
          <h2 className="font-medium">
            Client-side fetch{" "}
            <span className="text-zinc-500">(runs in your browser)</span>
          </h2>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="rounded-md border border-zinc-300 px-3 py-1 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error ? (
        <div className="mt-4 text-sm">
          <p className="font-mono text-red-600 dark:text-red-400">{error}</p>
          <p className="mt-2 text-zinc-500">
            Open the DevTools console for the real reason. The server answered
            fine &mdash; check the uvicorn log and you will see{" "}
            <code>200 OK</code>. Your browser discarded the response.
          </p>
        </div>
      ) : data ? (
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-zinc-500">Status</dt>
          <dd className="font-mono">{data.status}</dd>

          <dt className="text-zinc-500">Database</dt>
          <dd className="font-mono">{data.database}</dd>

          <dt className="text-zinc-500">Postgres clock</dt>
          <dd className="font-mono">{data.database_time}</dd>
        </dl>
      ) : (
        <p className="mt-4 text-sm text-zinc-500">Requesting...</p>
      )}

      <p className="mt-4 text-xs leading-relaxed text-zinc-500">
        Unlike the panel above, this request <strong>will</strong> appear in
        Chrome&apos;s Network tab &mdash; the browser made it. Press Refresh and
        watch a new entry appear.
      </p>
    </section>
  );
}
