import { NextResponse, type NextRequest } from "next/server";

/**
 * Route guard (Next 16 calls this `proxy`; it was `middleware` before).
 *
 * Runs on the server before a protected page renders, so a
 * logged-out visitor never receives its HTML at all -- unlike a client-side
 * redirect, which ships the page and then hides it.
 *
 * Only possible because next.config.ts proxies the API through this origin:
 * the auth cookie is first-party, so middleware here can see it. A cookie set
 * directly by the backend's domain would be invisible to this code.
 */

const PROTECTED = ["/account"];

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  // Presence only. Middleware deliberately does NOT verify the signature:
  // that needs the secret, which must never be in a frontend deploy. This is a
  // UX redirect, not a security boundary -- the real check is get_current_user
  // on the backend, which runs on every protected request regardless.
  if (request.cookies.has("access_token")) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  // So login can send them back where they were headed.
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  // Skip static assets and the API proxy, or every image would pay for this.
  matcher: ["/((?!_next/static|_next/image|api/backend|favicon.ico).*)"],
};
