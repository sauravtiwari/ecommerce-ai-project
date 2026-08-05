/**
 * Product detail page. The [id] folder makes this a dynamic route, so
 * /products/1 and /products/42 both render here.
 */

import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchProduct, formatPrice } from "@/lib/api";

export default async function ProductDetailPage({
  params,
}: {
  // Also a Promise in Next.js 16.
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = await fetchProduct(Number(id));

  // Turns the API's 404 into a real 404 page and status code, rather than
  // rendering an empty shell that looks broken.
  if (!product) notFound();

  return (
    <main className="mx-auto max-w-3xl p-8">
      <Link
        href={`/products?category=${product.category.slug}`}
        className="text-sm text-zinc-500 hover:underline"
      >
        &larr; Back to {product.category.name}
      </Link>

      <article className="mt-6">
        <span className="text-xs uppercase tracking-wide text-zinc-500">
          {product.category.name}
        </span>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {product.name}
        </h1>

        <p className="mt-4 text-2xl font-semibold">
          {formatPrice(product.price)}
        </p>

        {product.description && (
          <p className="mt-6 leading-relaxed text-zinc-600 dark:text-zinc-400">
            {product.description}
          </p>
        )}

        <dl className="mt-8 grid grid-cols-[auto_1fr] gap-x-8 gap-y-3 border-t border-zinc-200 pt-6 text-sm dark:border-zinc-800">
          <dt className="text-zinc-500">Stock</dt>
          <dd className="font-mono">
            {product.stock > 0 ? `${product.stock} available` : "Sold out"}
          </dd>

          <dt className="text-zinc-500">Status</dt>
          <dd className="font-mono">
            {product.is_active ? "Active" : "Inactive"}
          </dd>

          <dt className="text-zinc-500">Slug</dt>
          <dd className="font-mono">{product.slug}</dd>

          <dt className="text-zinc-500">Added</dt>
          <dd className="font-mono">
            {new Date(product.created_at).toLocaleDateString()}
          </dd>
        </dl>
      </article>
    </main>
  );
}
