"use client";

import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { ApiError, login, register } from "@/lib/api";

/**
 * Client Component: it holds form state and handles a submit event, neither of
 * which exists on the server. The pages that render it stay Server Components.
 */
export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isRegister = mode === "register";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);

    try {
      if (isRegister) {
        await register(email, password, fullName);
      } else {
        await login(email, password);
      }
      // No token to store: it arrived as an httpOnly cookie this code cannot
      // read, and the browser now attaches it automatically.
      //
      // refresh() re-runs middleware and Server Components with the new cookie.
      // Without it Next may serve the cached logged-out render of the target.
      router.replace(searchParams.get("next") || "/account");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Something went wrong. Try again.",
      );
      setPending(false);
    }
  }

  const inputClass =
    "w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {isRegister && (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Name</span>
          <input
            className={inputClass}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
          />
        </label>
      )}

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Email</span>
        <input
          className={inputClass}
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Password</span>
        <input
          className={inputClass}
          type="password"
          required
          // Mirrors the backend rule so the user hears about it before a round
          // trip. The server still enforces it -- this is convenience only.
          minLength={isRegister ? 8 : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          // Tells password managers which flow this is.
          autoComplete={isRegister ? "new-password" : "current-password"}
        />
        {isRegister && (
          <span className="text-xs text-zinc-500">At least 8 characters.</span>
        )}
      </label>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "Working…" : isRegister ? "Create account" : "Sign in"}
      </button>

      <p className="text-center text-sm text-zinc-500">
        {isRegister ? "Already have an account? " : "No account yet? "}
        <Link
          href={isRegister ? "/login" : "/register"}
          className="underline underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          {isRegister ? "Sign in" : "Create one"}
        </Link>
      </p>
    </form>
  );
}
