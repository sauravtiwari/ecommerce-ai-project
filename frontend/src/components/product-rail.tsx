/**
 * A horizontal rail of recommended products -- a Server Component.
 *
 * Takes already-fetched data as a prop rather than fetching itself, so the
 * caller decides which strategy to show and the component only renders.
 */

import Link from "next/link";

import { formatPrice, type RecommendedProduct } from "@/lib/api";

export default function ProductRail({
  title,
  subtitle,
  items,
  showScore = false,
}: {
  title: string;
  subtitle?: string;
  items: RecommendedProduct[];
  showScore?: boolean;
}) {
  if (items.length === 0) return null;

  return (
    <section className="mt-10">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <span className="font-mono text-xs text-zinc-500">{subtitle}</span>
        )}
      </div>

      {/* Scrolls horizontally rather than wrapping, so a rail stays one row on
          any width. */}
      <ul className="flex gap-4 overflow-x-auto pb-2">
        {items.map(({ product, score }, index) => (
          <li key={product.id} className="w-56 shrink-0">
            <Link
              href={`/products/${product.id}`}
              className="flex h-full flex-col justify-between rounded-lg border border-zinc-200 p-4 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-zinc-400">
                    #{index + 1}
                  </span>
                  <span className="text-xs uppercase tracking-wide text-zinc-500">
                    {product.category.name}
                  </span>
                </div>
                <h3 className="mt-1 text-sm font-medium">{product.name}</h3>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="font-semibold">{formatPrice(product.price)}</span>
                {showScore && (
                  <span className="font-mono text-xs text-zinc-500">
                    {score.toFixed(1)}
                  </span>
                )}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
