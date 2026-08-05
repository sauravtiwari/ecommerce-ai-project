"""Compare the query plan for a category filter: natural, forced-index, and
with the index actually dropped.

Run from backend/:  python -m scripts.explain_index

Everything happens inside one transaction, using SAVEPOINTs to undo each step,
finishing with ROLLBACK -- so the real schema is never touched.
"""

import asyncio

import asyncpg

from app.config import get_settings

QUERY = "SELECT * FROM products WHERE category_id = 1"


async def explain(conn: asyncpg.Connection, label: str) -> None:
    print(f"\n--- {label} ---")
    rows = await conn.fetch(f"EXPLAIN ANALYZE {QUERY}")
    for r in rows:
        print(" ", r["QUERY PLAN"])


async def main() -> None:
    plain = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(plain)

    async with conn.transaction():
        # 1. The planner's own choice, index present.
        await explain(conn, "1) index present, planner's free choice")

        # 2. Same index, but force Postgres to use it anyway -- shows the
        #    cost of the plan the index WOULD enable, for comparison.
        await conn.execute("SAVEPOINT before_forced")
        await conn.execute("SET LOCAL enable_seqscan = off")
        await explain(conn, "2) index present, forced to use it")
        await conn.execute("ROLLBACK TO SAVEPOINT before_forced")

        # 3. Remove the index entirely.
        await conn.execute("SAVEPOINT before_drop")
        await conn.execute("DROP INDEX ix_products_category_id")
        await explain(conn, "3) index dropped -- only a sequential scan is possible")
        await conn.execute("ROLLBACK TO SAVEPOINT before_drop")

    # Transaction never committed: the index is exactly as it was before this
    # script ran.
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
