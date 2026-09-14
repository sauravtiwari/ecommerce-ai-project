/**
 * Product catalog -- a Server Component.
 *
 * Fetches on the server, so the HTML arrives with products already in it and
 * the browser makes no API call. Category filtering is driven by the URL
 * (?category=shirts), which keeps it shareable and bookmarkable.
 */

import Link from "next/link";

import ProductRail from "@/components/product-rail";
import { fetchProducts, fetchTrending, formatPrice } from "@/lib/api";

const PAGE_SIZE = 12;

const CATEGORIES = [
  { slug: "", name: "All" },
  { slug: "accessories", name: "Accessories" },
  { slug: "shirts", name: "Shirts" },
  { slug: "footwear", name: "Footwear" },
  { slug: "bags", name: "Bags" },
  { slug: "outerwear", name: "Outerwear" },
];

export default async function ProductsPage({
  searchParams,
}: {
  // A Promise in Next.js 16 -- it must be awaited before use.
  searchParams: Promise<{ category?: string; page?: string }>;
}) {
  const { category, page } = await searchParams;
  const currentPage = Math.max(1, Number(page) || 1);

  // Both requests start before either is awaited, so they run in parallel
  // rather than one after the other.
  const productsPromise = fetchProducts({
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
    categorySlug: category,
  });
  const trendingPromise = fetchTrending(8);

  const [data, trending] = await Promise.all([productsPromise, trendingPromise]);

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  // Preserve the active category when paging.
  const pageHref = (n: number) =>
    `/products?${new URLSearchParams({
      ...(category ? { category } : {}),
      ...(n > 1 ? { page: String(n) } : {}),
    })}`;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Catalog</h1>
        <p className="mt-2 text-sm text-zinc-500">
          {data.total} product{data.total === 1 ? "" : "s"}
          {category ? ` in ${category}` : ""}
        </p>
      </header>

      <ProductRail
        title="Trending Now"
        subtitle={trending.strategy}
        items={trending.items}
        showScore
      />

      <nav className="mb-8 mt-10 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => {
          const active = (category ?? "") === c.slug;
          return (
            <Link
              key={c.slug || "all"}
              href={c.slug ? `/products?category=${c.slug}` : "/products"}
              className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
                active
                  ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                  : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
              }`}
            >
              {c.name}
            </Link>
          );
        })}
      </nav>

      {data.items.length === 0 ? (
        <p className="text-zinc-500">No products found.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((product) => (
            <li key={product.id}>
              <Link
                href={`/products/${product.id}`}
                className="flex h-full flex-col justify-between rounded-lg border border-zinc-200 p-5 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
              >
                <div>
                  <span className="text-xs uppercase tracking-wide text-zinc-500">
                    {product.category.name}
                  </span>
                  <h2 className="mt-1 font-medium">{product.name}</h2>
                </div>
                <div className="mt-4 flex items-baseline justify-between">
                  <span className="text-lg font-semibold">
                    {formatPrice(product.price)}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {product.stock > 0 ? `${product.stock} in stock` : "Sold out"}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {totalPages > 1 && (
        <nav className="mt-10 flex items-center justify-center gap-4 text-sm">
          {currentPage > 1 ? (
            <Link href={pageHref(currentPage - 1)} className="hover:underline">
              &larr; Previous
            </Link>
          ) : (
            <span className="text-zinc-400">&larr; Previous</span>
          )}
          <span className="text-zinc-500">
            Page {currentPage} of {totalPages}
          </span>
          {currentPage < totalPages ? (
            <Link href={pageHref(currentPage + 1)} className="hover:underline">
              Next &rarr;
            </Link>
          ) : (
            <span className="text-zinc-400">Next &rarr;</span>
          )}
        </nav>
      )}
    </main>
  );
}
