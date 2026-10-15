/** Backend location and response types, shared by the server and client fetches. */

/**
 * Only NEXT_PUBLIC_* variables reach the browser bundle -- correct for a URL
 * the browser must know, never for a secret. Inlined at build time, so
 * changing it in Vercel requires a redeploy.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Where BROWSER requests go. Not the API's real URL: a same-origin path that
 * next.config.ts rewrites to the backend.
 *
 * This is what makes cookie auth work. A direct fetch to the API is cross-site,
 * so SameSite=Lax would drop the auth cookie and middleware could not read it.
 * Routed through here, everything is first-party. Server Components keep using
 * API_BASE_URL -- they have no cookies to lose and skip a pointless hop.
 */
export const BROWSER_API_BASE = "/api/backend";

/** Mirrors HealthResponse in backend/app/main.py; also published at /openapi.json. */
export type HealthResponse = {
  status: "ok" | "degraded";
  environment: string;
  database: string;
  database_time: string | null;
};

/** Mirrors CategoryRead in backend/app/schemas.py. */
export type Category = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
};

/**
 * Mirrors ProductRead. Note `price` is a string, not a number: the backend
 * stores NUMERIC(10,2) and JSON has no decimal type, so serializing to a
 * float would reintroduce rounding error.
 */
export type Product = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  price: string;
  stock: number;
  is_active: boolean;
  created_at: string;
  category: Category;
};

/** Mirrors ProductList -- the paginated envelope. */
export type ProductListResponse = {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
};

export type ProductFilters = {
  limit?: number;
  offset?: number;
  categorySlug?: string;
  minPrice?: string;
  maxPrice?: string;
};

export async function fetchProducts(
  filters: ProductFilters = {},
): Promise<ProductListResponse> {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters.offset !== undefined) params.set("offset", String(filters.offset));
  if (filters.categorySlug) params.set("category_slug", filters.categorySlug);
  if (filters.minPrice) params.set("min_price", filters.minPrice);
  if (filters.maxPrice) params.set("max_price", filters.maxPrice);

  const res = await fetch(`${API_BASE_URL}/products?${params}`, {
    // Always hit the API: the checkpoint requires that editing a row in
    // Postgres changes what the page shows on the next reload.
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to load products: HTTP ${res.status}`);
  return res.json();
}

/** Returns null on 404 so callers can render notFound() rather than crash. */
export async function fetchProduct(id: number): Promise<Product | null> {
  const res = await fetch(`${API_BASE_URL}/products/${id}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to load product: HTTP ${res.status}`);
  return res.json();
}

/** "29.99" -> "£29.99", without ever converting through a float. */
export function formatPrice(price: string): string {
  return `£${price}`;
}

// --- Recommendations (Phase 4) ---

/** Mirrors RecommendedProduct. `score` is exposed so a rail is debuggable. */
export type RecommendedProduct = {
  product: Product;
  score: number;
};

/** Mirrors RecommendationList. */
export type RecommendationResponse = {
  items: RecommendedProduct[];
  strategy: string;
  generated_at: string;
};

export async function fetchTrending(limit = 8): Promise<RecommendationResponse> {
  const res = await fetch(`${API_BASE_URL}/recommendations/trending?limit=${limit}`, {
    // Must not be cached: the checkpoint is that viewing a product repeatedly
    // moves it up this rail on the next reload.
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to load trending: HTTP ${res.status}`);
  return res.json();
}

export async function fetchSimilar(
  productId: number,
  limit = 4,
): Promise<RecommendationResponse | null> {
  const res = await fetch(
    `${API_BASE_URL}/recommendations/similar/${productId}?limit=${limit}`,
    { cache: "no-store" },
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to load similar: HTTP ${res.status}`);
  return res.json();
}

// --- Event tracking (Phase 4) ---

const SESSION_KEY = "ecommerce_session_id";

/**
 * A stable anonymous id for this browser, created on first use.
 *
 * Not authentication and not a secret -- just a way to group one visitor's
 * events before accounts exist in Phase 5. Browser-only: localStorage does not
 * exist on the server, so this must never be called during SSR.
 */
export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/**
 * Fire-and-forget event recording.
 *
 * Deliberately swallows errors: analytics failing must never break the page
 * the user is actually trying to read.
 */
export async function recordEvent(
  eventType: "view" | "add_to_cart",
  productId: number,
): Promise<void> {
  try {
    await fetch(`${BROWSER_API_BASE}/events`, {
      // Same-origin now, so the auth cookie rides along and the backend can
      // attribute this view to the signed-in account instead of a browser id.
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: eventType,
        product_id: productId,
        session_id: getSessionId(),
      }),
    });
  } catch {
    // Intentionally ignored.
  }
}


// --- Auth (Phase 5) ---

/** Mirrors UserRead in backend/app/schemas.py. */
export type User = {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
};

/** Mirrors AuthResponse. No token field: the tokens are httpOnly cookies. */
export type AuthResponse = {
  user: User;
  expires_in: number;
};

/** Thrown with the backend's own message so forms can show something useful. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function authRequest(
  path: string,
  body?: unknown,
): Promise<Response> {
  const res = await fetch(`${BROWSER_API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    // Tells fetch to accept and store the Set-Cookie coming back. Without it
    // login "succeeds" and the browser silently keeps no session.
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    // FastAPI puts a string in `detail` for HTTPException and an array of
    // field errors there for a 422.
    const message =
      typeof detail?.detail === "string"
        ? detail.detail
        : Array.isArray(detail?.detail)
          ? detail.detail[0]?.msg ?? "Invalid input"
          : `Request failed (HTTP ${res.status})`;
    throw new ApiError(message, res.status);
  }
  return res;
}

export async function register(
  email: string,
  password: string,
  fullName?: string,
): Promise<AuthResponse> {
  const res = await authRequest("/auth/register", {
    email,
    password,
    full_name: fullName || null,
  });
  return res.json();
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const res = await authRequest("/auth/login", { email, password });
  return res.json();
}

export async function logout(): Promise<void> {
  await authRequest("/auth/logout");
}

/** The signed-in user, or null. Used by client components to render state. */
export async function fetchMe(): Promise<User | null> {
  const res = await fetch(`${BROWSER_API_BASE}/auth/me`, {
    credentials: "include",
    cache: "no-store",
  });
  return res.ok ? res.json() : null;
}
