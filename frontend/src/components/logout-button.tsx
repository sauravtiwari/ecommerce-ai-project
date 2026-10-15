"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { logout } from "@/lib/api";

export default function LogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleLogout() {
    setPending(true);
    try {
      await logout();
    } catch {
      // Ignored on purpose: the server clears the cookies either way, and a
      // failed logout must never strand someone on a page they want to leave.
    }
    router.replace("/");
    // Re-runs middleware and every Server Component without the cookie.
    // Skipping this leaves the cached signed-in render on screen.
    router.refresh();
  }

  return (
    <button
      onClick={handleLogout}
      disabled={pending}
      className="self-start rounded-md border border-zinc-300 px-4 py-2 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
    >
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}
