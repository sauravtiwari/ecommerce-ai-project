"use client";

/**
 * Records a `view` event when a product page is opened.
 *
 * Renders nothing -- it exists purely for the side effect. A Client Component
 * because it needs useEffect and localStorage, neither of which exists on the
 * server.
 */

import { useEffect, useRef } from "react";

import { recordEvent } from "@/lib/api";

export default function ViewTracker({ productId }: { productId: number }) {
  // React StrictMode deliberately runs effects twice in development to surface
  // bugs. Without this guard every dev page load would log two views and
  // quietly skew the data the recommenders read.
  const recorded = useRef<number | null>(null);

  useEffect(() => {
    if (recorded.current === productId) return;
    recorded.current = productId;
    recordEvent("view", productId);
  }, [productId]);

  return null;
}
