"""Generate synthetic browsing history so the recommenders have something to read.

Run from backend/:  python -m scripts.seed_events [--reset] [--days 30]

Real traffic does not exist yet, so this fabricates it -- but not uniformly at
random, because uniform noise is unpredictable by construction and would make
every recommender score the same as chance. Real behaviour has structure:

  * popularity is heavily skewed (a few products get most of the attention)
  * that skew SHIFTS over time (today's hit was not last month's)
  * a visitor looks at several products in one session
  * a small fraction of views become cart-adds

The first two are what a popularity recommender can actually learn; the shift
is what makes recency decay worth having rather than just counting forever.

Deterministic: a fixed seed means the eval numbers are reproducible.
"""

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select

from app.db import SessionLocal, engine
from app.models import Event, Product

SEED = 20260912
SESSIONS_PER_DAY = 40
# Products whose popularity climbs over the window, so the recent past does not
# look like the distant past.
RISING_COUNT = 6
CART_ADD_RATE = 0.18


def build_weights(product_ids: list[int], rng: random.Random) -> tuple[dict, set]:
    """Zipf-ish base popularity, plus a set of products that trend upward."""
    shuffled = product_ids[:]
    rng.shuffle(shuffled)
    # 1/rank: product at rank 1 gets ~50x the weight of rank 50.
    base = {pid: 1.0 / (rank + 1) for rank, pid in enumerate(shuffled)}
    rising = set(rng.sample(product_ids, min(RISING_COUNT, len(product_ids))))
    return base, rising


def weight_at(pid: int, base: dict, rising: set, progress: float) -> float:
    """Weight of a product at `progress` (0.0 = window start, 1.0 = now).

    Rising products gain up to 12x by the end of the window; everything else
    stays flat. That gradient is the signal a decayed count can pick up and a
    raw all-time count cannot.
    """
    w = base[pid]
    if pid in rising:
        w *= 1.0 + 11.0 * progress
    return w


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete existing events first")
    parser.add_argument("--days", type=int, default=30, help="how far back to generate")
    args = parser.parse_args()

    rng = random.Random(SEED)

    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Event))
        if existing and not args.reset:
            print(f"{existing} events already exist. Pass --reset to regenerate.")
            return
        if args.reset and existing:
            await session.execute(delete(Event))
            print(f"deleted {existing} existing events")

        product_ids = list((await session.scalars(select(Product.id))).all())
        if not product_ids:
            print("No products. Run `python -m scripts.seed` first.")
            return

        base, rising = build_weights(product_ids, rng)

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=args.days)
        rows: list[dict] = []

        for day in range(args.days):
            day_start = window_start + timedelta(days=day)
            for _ in range(SESSIONS_PER_DAY):
                session_id = f"seed-{rng.randrange(10**12):012d}"
                # Events within a session happen minutes apart, not days.
                t = day_start + timedelta(
                    hours=rng.uniform(0, 24), minutes=rng.uniform(0, 60)
                )
                progress = (t - window_start).total_seconds() / (
                    now - window_start
                ).total_seconds()

                weights = [weight_at(p, base, rising, progress) for p in product_ids]
                viewed = rng.choices(product_ids, weights=weights, k=rng.randint(1, 5))

                for pid in viewed:
                    t += timedelta(seconds=rng.uniform(20, 240))
                    if t > now:
                        break
                    rows.append(
                        {
                            "event_type": "view",
                            "product_id": pid,
                            "session_id": session_id,
                            "created_at": t,
                        }
                    )
                    if rng.random() < CART_ADD_RATE:
                        t += timedelta(seconds=rng.uniform(5, 60))
                        rows.append(
                            {
                                "event_type": "add_to_cart",
                                "product_id": pid,
                                "session_id": session_id,
                                "created_at": t,
                            }
                        )

        # One executemany rather than 4000 INSERT round trips.
        await session.execute(insert(Event), rows)
        await session.commit()

    views = sum(1 for r in rows if r["event_type"] == "view")
    carts = len(rows) - views
    print(f"inserted {len(rows)} events ({views} views, {carts} cart-adds)")
    print(f"window   : {args.days} days ending {now:%Y-%m-%d %H:%M} UTC")
    print(f"rising   : product ids {sorted(rising)}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
