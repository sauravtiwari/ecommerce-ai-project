"""Offline evaluation of recommenders against a fixed temporal split.

Run from backend/:  python -m scripts.eval_recs [--test-days 7] [--k 10]

THIS SCRIPT IS THE POINT OF PHASE 4. Every recommender built from here --
collaborative filtering, ALS, embeddings, the hybrid -- gets measured against
the same split and the same metrics, and has to beat what is printed here or
it has not earned its complexity.

Method
------
Split events by TIME, never randomly. A random split would let the model learn
from Tuesday to predict Monday, which is not a thing you can do in production.

    train:  events before the cutoff   -> what the recommender may see
    test:   events on/after the cutoff -> what it is trying to predict

Recommendations here are global (the same list for everybody), because there
are no user accounts until Phase 5. So a "hit" is: did the product a visitor
actually interacted with in the test period appear in our top-K?
"""

import argparse
import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Event, Product
from app.recommenders import DEFAULT_HALF_LIFE_HOURS, trending_statement

SEED = 20260912
RESULTS_PATH = Path(__file__).resolve().parents[1] / "eval_results" / "phase4_baseline.json"


def evaluate(recommended: list[int], truth: dict[str, set[int]], k: int) -> dict:
    """Precision@K, Recall@K and HitRate@K, averaged over test sessions."""
    if not truth:
        return {"precision_at_k": 0.0, "recall_at_k": 0.0, "hit_rate_at_k": 0.0, "sessions": 0}

    rec_set = set(recommended[:k])
    precisions, recalls, hits = [], [], []

    for actual in truth.values():
        overlap = len(rec_set & actual)
        # Precision: of the K slots we spent, how many were useful?
        precisions.append(overlap / k)
        # Recall: of what they actually wanted, how much did we surface?
        recalls.append(overlap / len(actual))
        # Hit rate: did we get at least one right? The most forgiving metric,
        # and the one closest to "was the rail useful at all".
        hits.append(1.0 if overlap else 0.0)

    n = len(truth)
    return {
        "precision_at_k": sum(precisions) / n,
        "recall_at_k": sum(recalls) / n,
        "hit_rate_at_k": sum(hits) / n,
        "sessions": n,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-days", type=int, default=7, help="length of the test window")
    parser.add_argument("--k", type=int, default=10, help="how many items a rail shows")
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="try a range of half-lives and print Precision@K for each",
    )
    args = parser.parse_args()

    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.test_days)

    async with SessionLocal() as session:
        product_ids = list((await session.scalars(select(Product.id))).all())

        # --- ground truth: what actually happened after the cutoff ---
        test_rows = (
            await session.execute(
                select(Event.session_id, Event.product_id).where(Event.created_at >= cutoff)
            )
        ).all()
        truth: dict[str, set[int]] = {}
        for session_id, product_id in test_rows:
            truth.setdefault(session_id, set()).add(product_id)

        train_count = await session.scalar(
            select(Event.id).where(Event.created_at < cutoff).limit(1)
        )
        if train_count is None:
            print("No training events before the cutoff. Run scripts.seed_events first.")
            return

        if args.sweep:
            print(f"\nhalf-life sweep  (test window = {args.test_days}d, K = {args.k})\n")
            print(f"{'half-life':>12}  {'Precision@K':>12}")
            print("-" * 28)
            for hl in (6, 12, 24, 48, 96, 168, 720, 1e9):
                rows = (
                    await session.execute(
                        trending_statement(
                            now=cutoff, before=cutoff, limit=args.k, half_life_hours=hl
                        )
                    )
                ).unique().all()
                m = evaluate([p.id for p, _ in rows], truth, args.k)
                label = "no decay" if hl > 1e8 else f"{hl:g}h"
                print(f"{label:>12}  {m['precision_at_k']:>12.4f}")
            await engine.dispose()
            return

        # --- candidate recommenders ---
        # `now=cutoff, before=cutoff` is the leakage guard: score as if standing
        # at the cutoff, seeing nothing after it.
        trending_rows = (
            await session.execute(
                trending_statement(
                    now=cutoff, before=cutoff, limit=args.k,
                    half_life_hours=DEFAULT_HALF_LIFE_HOURS,
                )
            )
        ).unique().all()

        # Same code path with decay effectively switched off -- isolates how
        # much the recency weighting is actually worth.
        popularity_rows = (
            await session.execute(
                trending_statement(
                    now=cutoff, before=cutoff, limit=args.k, half_life_hours=1e9
                )
            )
        ).unique().all()

    strategies = {
        "random": rng.sample(product_ids, min(args.k, len(product_ids))),
        "popularity (no decay)": [p.id for p, _ in popularity_rows],
        f"trending (half-life {DEFAULT_HALF_LIFE_HOURS:g}h)": [p.id for p, _ in trending_rows],
    }

    results = {name: evaluate(ids, truth, args.k) for name, ids in strategies.items()}

    # --- report ---
    print(f"\nsplit cutoff : {cutoff:%Y-%m-%d %H:%M} UTC  (test window = {args.test_days}d)")
    print(f"test sessions: {len(truth)}   K = {args.k}\n")
    print(f"{'strategy':<32} {'Precision@K':>12} {'Recall@K':>10} {'HitRate@K':>11}")
    print("-" * 68)
    for name, m in results.items():
        print(
            f"{name:<32} {m['precision_at_k']:>12.4f} "
            f"{m['recall_at_k']:>10.4f} {m['hit_rate_at_k']:>11.4f}"
        )

    baseline = results["random"]["precision_at_k"]
    for name, m in results.items():
        if name == "random":
            continue
        lift = (m["precision_at_k"] / baseline - 1) * 100 if baseline else float("inf")
        print(f"\n{name}: {lift:+.1f}% Precision@K vs random")

    # --- persist, so later phases can compare against these exact numbers ---
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "phase": 4,
                "generated_at": now.isoformat(),
                "cutoff": cutoff.isoformat(),
                "test_days": args.test_days,
                "k": args.k,
                "test_sessions": len(truth),
                "results": results,
                "recommendations": strategies,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nsaved -> {RESULTS_PATH.relative_to(RESULTS_PATH.parents[1])}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
