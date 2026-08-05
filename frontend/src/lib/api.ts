/** Backend location and response types, shared by the server and client fetches. */

/**
 * Only NEXT_PUBLIC_* variables reach the browser bundle -- correct for a URL
 * the browser must know, never for a secret. Inlined at build time, so
 * changing it in Vercel requires a redeploy.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
