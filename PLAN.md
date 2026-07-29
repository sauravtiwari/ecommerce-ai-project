# AI Engineer Curriculum: E-Commerce Platform with a Recommendation System

**Stack:** Next.js 16 (App Router, React 19) · FastAPI (Pydantic v2, async) · PostgreSQL 18 + pgvector (HNSW indexes) · SQLAlchemy 2.0 async / asyncpg · Alembic · Docker · Vercel + Render/Fly.io

**Total: ~18–20 weeks part-time** (evenings + weekends)

---

## Operating principles for this whole plan

1. **Every phase ends with something running and clickable** — never a local-only exercise you have to trust blindly.
2. **Concepts are taught right before the feature that needs them**, not as abstract prerequisites you'll have forgotten by the time they matter.
3. **Every recommender from Phase 4 onward is measured against the same held-out data as the one before it.** "This is better" is always a number, never a feeling.
4. **Testing and basic security are habits built each phase**, not a unit bolted on at the end.

---

## Phase 0: Machine Setup (specific to this machine)

Already present: Node.js v24.18.0, npm 11.16.0, Python 3.13.14, PostgreSQL 18 (service running).

Still needed:

- **Git** — `winget install --id Git.Git -e` (blocker; nothing else should start first)
- **`psql` on PATH** — add `C:\Program Files\PostgreSQL\18\bin` to your user PATH
- **pgvector for Postgres 18** — needed in Phase 9. On Windows this is the fiddliest install in the project; plan a dedicated session, or switch to a hosted Postgres (Neon/Supabase, pgvector preinstalled) if it fights you.
- **Docker Desktop** — not needed until Phase 12. Use your native Postgres 18 until then.

**Time:** 1–2 hours.

---

## Phase 1: Environment, Tooling & the Full-Stack Skateboard

**Learn first:** the client–server split, HTTP request/response cycle, JSON as the wire format, CORS, environment variables/secrets management, and a real git workflow (feature branches, meaningful commits, merging). The biggest early failure mode isn't a bad algorithm — it's a broken environment or an afternoon lost to an untracked change.

**Build:** scaffold Next.js and a one-route FastAPI app; point FastAPI at your local Postgres 18 with `.env`-managed credentials (`pydantic-settings`); deploy the frontend to Vercel and the backend to Render/Fly.io with a hosted Postgres; wire a `fetch()` from a Next.js page to a FastAPI `/health` endpoint that queries the database.

**Checkpoint:** the live Vercel URL displays text that actually came from your separately deployed FastAPI service and database. Make one intentional branch, commit, and merge. Explain what breaks if CORS is misconfigured.

**Time:** 3–5 hours.

---

## Phase 2: Relational Modeling & the Product Catalog

**Learn first:** ER modeling and normalization (1NF–3NF), why indexes matter, migrations as versioned schema history, and how an ORM (SQLAlchemy 2.0 async) maps to the SQL underneath. See the schema and the query plan with your own eyes before anything hides them from you.

**Build:** design `products` and `categories`; write your first Alembic migration; seed ~50 products; build `GET/POST /products` with Pydantic schemas; render a catalog grid and a `/products/[id]` detail page in Next.js — your first real server-component vs. client-component decision (note it, you'll need this distinction constantly). Write your first pytest test against a CRUD endpoint.

**Checkpoint:** editing a row directly in the DB changes what the live site shows. Run `EXPLAIN ANALYZE` on a category filter query with and without an index and explain the difference in the plan. Your pytest test passes, and fails correctly when you break the endpoint on purpose.

**Time:** 1.5–2 weeks.

---

## Phase 3: Async Internals, Validation & API Robustness

**Learn first:** ASGI vs. WSGI and what the event loop actually does; why a *blocking* call inside `async def` serializes every request on that worker; dependency injection in FastAPI; input validation as a security boundary (rejecting malformed payloads, parameterized queries against SQL injection); basic rate limiting. This is where "async is fast" stops being a slogan and becomes something you can prove.

**Build:** pagination and filtering on `/products`; refactor to a clean async DB session via dependency injection; write a script that hits an endpoint concurrently and compare throughput with a deliberately blocking call vs. proper `asyncpg`; add a rate limit to a public endpoint; expand tests to cover bad-payload rejection.

**Checkpoint:** your load test shows the throughput gap and you can explain *why* in terms of the event loop. Tests confirm malformed requests return correct status codes, not 500s.

**Time:** 1–1.5 weeks.

---

## Phase 4: Simple Recommendations — Popularity, Rules & Your First Eval

**Learn first:** implicit feedback (views and cart-adds are signal even without star ratings), the cold-start problem, count-based ranking with recency decay, and — critically — the discipline of evaluating against a baseline *starting now*, not at the end. Every recommender from here must beat this one on the same data split, or it hasn't earned its complexity.

**Build:** an `events` table logging `view` / `add_to_cart` from the frontend; `GET /recommendations/trending` (top-N by decayed count); a same-category "similar products" fallback; a homepage "Trending Now" rail. Write a small eval script: split events by time, compute Precision@10 for trending vs. a random-item baseline, save the numbers. **This split and this script get reused every phase from here forward.**

**Checkpoint:** repeatedly viewing one product visibly moves it up the live rail. Your eval script shows trending beating random, with a printed number you can point back to later.

**Time:** 1 week.

---

## Phase 5: Accounts, Auth & Security

**Learn first:** password hashing, JWT vs. session cookies (and why `httpOnly` matters), CSRF/XSS basics, token expiry and refresh strategy. First phase where a bug means real user harm, not just a wrong number on a page.

**Build:** `users` table; `/auth/register` and `/auth/login`; a FastAPI dependency for `get_current_user` guarding protected routes; Next.js middleware redirecting logged-out users; a login-specific rate limit for brute-force protection. Tests for valid/invalid credentials and rejection of unauthenticated requests.

**Checkpoint:** register → logout → hit a protected page (rejected) → login → same page works, live. State your token expiry/refresh choice and justify it.

**Time:** 1–1.5 weeks.

---

## Phase 6: Cart, Checkout & Transactional Integrity

**Learn first:** ACID transactions and idempotent writes. This is where "silently corrupting an order" becomes a real risk you design against, not a textbook example.

**Build:** cart state; `orders` / `order_items` schema; `POST /orders` wrapped in a single DB transaction; an order-history page; extend `events` with a `purchase` type (fuel for every collaborative recommender that follows). Add a test simulating a mid-write failure that asserts nothing partial was committed.

**Checkpoint:** kill the server mid-checkout and confirm the transaction rolled back cleanly. Place a real order and verify the rows in Postgres and in the UI history.

**Time:** 1.5–2 weeks.

---

## Phase 7: Collaborative Filtering — Learning From Behavior

**Learn first:** the user–item interaction matrix, cosine/Jaccard similarity, why item–item CF scales better than user–user in e-commerce, and the sparsity problem you'll hit on small real data. This is the conceptual bridge from *counting* to *learned* personalization.

**Build:** a market-basket "bought together" query (self-join on `order_items`); an offline job (numpy/scipy) computing item–item similarity from `events`, stored in an `item_similarities` table; `GET /recommendations/similar-items/{id}`; a "Because you viewed X" rail.

**Checkpoint:** compute cosine similarity by hand on a small toy matrix and confirm your code matches. Using the same split from Phase 4, hold out each user's last purchase and measure Hit Rate@10. CF should beat the popularity baseline — and if it doesn't yet, be able to say why (sparsity).

**Time:** 1.5–2 weeks.

---

## Phase 8: Matrix Factorization — Latent Factors at Scale

**Learn first:** the intuition behind SVD/ALS (users and items projected into a shared latent space), implicit-feedback confidence weighting (Hu/Koren/Volinsky), and a first dose of resource awareness — training cost and memory grow with catalog and user size.

**Build:** implicit ALS via the `implicit` library on your interaction matrix; persist user/item factor vectors; `GET /recommendations/for-you/{user_id}`, gated behind login, as a dot product over item vectors.

**Checkpoint:** on the same held-out split, compare Recall@K / MAP@K against Phase 7. Explain in your own words what a latent factor represents. Identify the cold-start users where ALS still loses to CF or popularity, and explain why.

**Time:** 2 weeks.

---

## Phase 9: Content-Based Filtering, Embeddings & pgvector

**Learn first:** representing items by their own content (TF-IDF, then dense learned embeddings) rather than behavior — this is what solves cold start for brand-new products with zero interactions, which nothing so far can touch. Also HNSW approximate vs. exact search trade-offs, and the cost/latency trade-off of batch vs. on-demand embedding generation.

**Build:** enable `pgvector`; add an `embedding` column to `products`; generate embeddings from title/description in a batch job; create an HNSW index (`vector_cosine_ops`); `GET /recommendations/similar-content/{id}` using the `<=>` operator; compare against the Phase 4 rule-based "similar" rail on the same page.

**Checkpoint:** insert a brand-new product with zero interactions and show it still returns sensible similar items — unlike Phases 7–8. Benchmark query latency with and without the HNSW index and explain the recall/speed trade-off.

**Time:** 2 weeks.

---

## Phase 10: Hybrid Recommenders, Context & Rigorous Evaluation

**Learn first:** production recommenders are retrieve-then-rank *pipelines*, never one model. Combine popularity, CF, ALS, and content candidates, then blend or learn-to-rank with business filters (in stock, exclude already-purchased). Formalize what you've done informally since Phase 4: temporal splitting without leakage, Precision@K / Recall@K / MAP / NDCG, coverage and diversity — and why session/recency context (what the user is looking at *right now*) beats a static profile.

**Build:** a recommendation service unioning candidates from every prior phase with a weighted (or small LightGBM) ranking layer; a session-aware re-score using recently viewed items; a single reusable `offline_eval.py` that reruns *every* recommender you've built against one fixed split and prints a comparison table.

**Checkpoint:** the hybrid beats every individual method on both cold-start and warm-user segments — show one concrete case. Rerunning the harness reproduces identical numbers. Explain why NDCG penalizes correctly-relevant-but-poorly-ranked items while Recall@K doesn't, and use the harness to catch one "too good to be true" leakage bug.

**Time:** 2–2.5 weeks.

---

## Phase 11: Productionization — Caching, A/B Testing & Monitoring

**Learn first:** offline metrics don't guarantee online lift — real teams validate with experiments. Also cache invalidation, config-as-code, and why recommenders degrade silently as behavior shifts if nobody watches them.

**Build:** cache hot recommendation queries (Redis or in-memory); log impressions/clicks for online CTR; hash users into A/B buckets serving two recommenders, with a basic significance check; a small dashboard tracking CTR trend and flagging staleness; a `runs` table recording which model/config/version is live.

**Checkpoint:** show cache hit/miss metrics and an online CTR comparison between variants — with an honest discussion of whether you have enough traffic to trust it. The dashboard correctly flags a deliberately staled model. Any live recommendation traces back to an exact model version.

**Time:** 1.5–2 weeks.

---

## Phase 12: Containerize, CI/CD & Ship a Portfolio-Ready Product

**Learn first:** a project isn't reproducibly real until anyone can run it anywhere — multi-stage Docker builds, Compose orchestration, and CI that runs tests before it deploys.

**Build:** Dockerfiles for FastAPI and Next.js plus a full `docker-compose` stack with Postgres; a GitHub Actions workflow running your full pytest suite (CRUD, auth, transactions, recommender edge cases, eval reproducibility) then auto-deploying on push; a README, architecture diagram, and short demo walkthrough; a written "what I'd do at 10x scale" note.

**Checkpoint:** `docker compose up` runs the entire stack locally; a pushed commit triggers tests then a live auto-deploy; you can explain the whole system — data flow, auth, and how recommendations evolved from rules to hybrid ML — in five minutes without notes.

**Time:** 1.5–2 weeks.

---

## Keep Growing From Here

Frame the finished project as a portfolio centerpiece, not a closed box. The README and architecture doc from Phase 12 should read like a system-design interview answer, and the metric table from Phase 10 is your proof that every decision was measured, not guessed. When discussing it, lead with the **arc** — popularity baseline → CF → matrix factorization → embeddings → hybrid — because that progression, plus real Precision/NDCG deltas at each step, is what separates genuine applied ML engineering from "I added a recommend button."

Worthwhile next directions:

- **Session-based deep models** (GRU4Rec, transformer-based sequential recommenders) as a successor to Phase 10's context tricks
- **Learning-to-rank properly** (LambdaMART, pairwise/listwise losses) instead of hand-weighted blending
- **A real feature store and streaming pipeline** (Kafka/Flink) for near-real-time personalization instead of nightly batch
- **Causal inference and counterfactual evaluation** (off-policy evaluation, not just offline splits)
- **Scaling vector search** past a single Postgres instance (sharded pgvector, or a dedicated ANN service)
- **LLM-based product search / RAG** on top of your existing embeddings as a complementary retrieval path

Each is a natural "Phase 13" for a specific résumé target — pick the one nearest the job you want next.
