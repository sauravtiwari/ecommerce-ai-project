"""Recommendation strategies.

Query construction lives here, not in the router, because the offline eval
script must score with exactly the same code the API serves. If the two drift,
your measured numbers describe a system you are not running.
"""

from datetime import datetime

from sqlalchemy import Select, case, desc, func, select
from sqlalchemy.orm import contains_eager

from app.models import Category, Event, Product

# How much each signal counts. A cart-add is a stronger statement of intent
# than a view, and a purchase stronger still. These are judgement calls, not
# derived values -- which is exactly why they live in one named place where
# they can be tuned and their effect measured.
EVENT_WEIGHTS: dict[str, float] = {
    "view": 1.0,
    "add_to_cart": 3.0,
    "purchase": 5.0,
}

# Hours for an event's contribution to halve.
#
# 96h, chosen by measurement rather than taste: scripts/eval_recs.py --sweep
# showed Precision@10 rising from 0.1480 (6h) to 0.1548 (96h) and flat after.
# At ~140 events/day over 50 products, a short half-life ranks on ~130 events
# and the estimate is simply too noisy -- variance costs more than staleness.
#
# Re-run the sweep once real traffic exists. Genuine trends spike far more
# sharply than seeded ones, which should favour a shorter half-life.
DEFAULT_HALF_LIFE_HOURS = 96.0


def trending_statement(
    *,
    now: datetime,
    limit: int = 10,
    half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
    before: datetime | None = None,
) -> Select:
    """Top products by time-decayed, weighted event count.

    score(product) = SUM over its events of  weight * 0.5 ^ (age_hours / half_life)

    `now` is the reference point decay is measured from, and is passed in
    rather than read inside: the eval script sets it to the train/test cutoff
    so that scoring a "past" moment behaves exactly as it did at the time.

    `before` excludes later events entirely. That is the leakage guard -- an
    offline evaluation must not be able to see the future it is predicting.
    """
    age_hours = func.extract("epoch", now - Event.created_at) / 3600.0

    weight = case(
        *[(Event.event_type == name, w) for name, w in EVENT_WEIGHTS.items()],
        else_=1.0,
    )

    # func.power(0.5, x) -> Postgres POWER(0.5, x). Aggregated in SQL rather
    # than in Python so only the top N rows cross the network.
    score = func.sum(weight * func.power(0.5, age_hours / half_life_hours))

    stmt = (
        select(Product, score.label("score"))
        .join(Event, Event.product_id == Product.id)
        .join(Product.category)
        .options(contains_eager(Product.category))
        .where(Product.is_active.is_(True))
        # Grouping by both primary keys makes every other column of both tables
        # functionally dependent on the group, which Postgres allows.
        .group_by(Product.id, Category.id)
        .order_by(desc("score"))
        .limit(limit)
    )

    if before is not None:
        stmt = stmt.where(Event.created_at < before)

    return stmt


def similar_products_statement(
    *,
    product: Product,
    limit: int = 10,
) -> Select:
    """Rule-based fallback: same category, nearest price.

    Deliberately uses no event data at all, so it still works for a product
    nobody has ever viewed. That is the cold-start problem: every behavioural
    recommender from Phase 7 onward returns nothing for a brand-new item, and
    this is what covers the gap until embeddings arrive in Phase 9.
    """
    price_distance = func.abs(Product.price - product.price)

    return (
        select(Product, (-price_distance).label("score"))
        .join(Product.category)
        .options(contains_eager(Product.category))
        .where(
            Product.category_id == product.category_id,
            Product.id != product.id,
            Product.is_active.is_(True),
        )
        .order_by(price_distance, Product.id)
        .limit(limit)
    )
