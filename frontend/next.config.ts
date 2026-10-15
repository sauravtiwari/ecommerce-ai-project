import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Browser calls go to /api/backend/* on THIS origin, and Next forwards
        // them to FastAPI. That makes the auth cookie first-party:
        //
        //   direct  browser -> localhost:3000 ... fetch -> 127.0.0.1:8000
        //           cross-site, so SameSite=Lax drops the cookie, and
        //           middleware on :3000 cannot read a cookie set by :8000.
        //
        //   proxied browser -> localhost:3000 ... fetch -> localhost:3000
        //           same-origin. The cookie is sent, middleware can read it,
        //           and SameSite=Lax keeps its CSRF protection intact.
        //
        // Same reasoning in production (vercel.app vs onrender.com), where the
        // two are unambiguously different sites.
        source: "/api/backend/:path*",
        destination: `${API_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
