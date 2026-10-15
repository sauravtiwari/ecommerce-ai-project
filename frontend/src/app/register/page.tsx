import { Suspense } from "react";
import Link from "next/link";

import AuthForm from "@/components/auth-form";

export const metadata = { title: "Create account" };

/**
 * Server Component wrapper. Suspense is required: AuthForm calls
 * useSearchParams(), which forces a client boundary Next must be told about.
 */
export default function RegisterPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 p-8">
      <div>
        <Link href="/" className="text-sm text-zinc-500 hover:underline">
          &larr; Home
        </Link>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">Create your account</h1>
      </div>
      <Suspense>
        <AuthForm mode="register" />
      </Suspense>
    </main>
  );
}
