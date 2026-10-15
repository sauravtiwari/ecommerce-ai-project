import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import LogoutButton from "@/components/logout-button";
import { API_BASE_URL, type User } from "@/lib/api";

export const metadata = { title: "Your account" };

/**
 * The protected page from the Phase 5 checkpoint.
 *
 * A Server Component, so it asks the backend who the caller is before rendering
 * anything. Middleware already redirected logged-out visitors, but that only
 * checked that a cookie *exists* -- it never verified the signature. This is
 * where a forged or expired token is actually caught.
 *
 * Two independent gates, on purpose: middleware for a fast redirect, the
 * backend for the real answer. Only the second one is a security boundary.
 */
export default async function AccountPage() {
  // Server Components have no browser to attach cookies for them, so the
  // incoming request's cookies are forwarded by hand. Going direct to
  // API_BASE_URL here rather than through the proxy: this code already runs on
  // the server, so the same-origin hop buys nothing.
  const cookieHeader = (await cookies()).toString();

  const res = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { cookie: cookieHeader },
    cache: "no-store", // never cache one user's identity and serve it to another
  });

  // Covers the case middleware cannot: a cookie that is present but invalid,
  // expired, or belongs to a deleted account.
  if (!res.ok) redirect("/login?next=/account");

  const user: User = await res.json();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-lg flex-col justify-center gap-6 p-8">
      <div>
        <Link href="/" className="text-sm text-zinc-500 hover:underline">
          &larr; Home
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">
          {user.full_name ? `Hello, ${user.full_name}` : "Your account"}
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          This page is only reachable while signed in.
        </p>
      </div>

      <dl className="divide-y divide-zinc-200 rounded-md border border-zinc-200 text-sm dark:divide-zinc-800 dark:border-zinc-800">
        {[
          ["Email", user.email],
          ["User ID", String(user.id)],
          ["Member since", new Date(user.created_at).toLocaleDateString()],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 px-4 py-3">
            <dt className="text-zinc-500">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>

      <p className="text-xs text-zinc-500">
        Your views are now recorded against this account rather than an
        anonymous browser id &mdash; which is what the collaborative filtering
        in Phase 7 needs.
      </p>

      <LogoutButton />
    </main>
  );
}
