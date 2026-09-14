"""Tests for event recording and the Phase 4 recommenders."""

from httpx import AsyncClient


# --- POST /events ---

async def test_record_view_event_returns_201(client: AsyncClient):
    res = await client.post(
        "/events",
        json={"event_type": "view", "product_id": 1, "session_id": "pytest-session-1"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["event_type"] == "view"
    assert body["product_id"] == 1
    assert body["id"] > 0


async def test_record_event_rejects_unknown_type(client: AsyncClient):
    res = await client.post(
        "/events",
        json={"event_type": "sneeze", "product_id": 1, "session_id": "pytest-session-1"},
    )

    # Literal in EventCreate rejects it before the CHECK constraint would.
    assert res.status_code == 422


async def test_record_event_rejects_missing_product(client: AsyncClient):
    res = await client.post(
        "/events",
        json={"event_type": "view", "product_id": 999999, "session_id": "pytest-sess"},
    )

    assert res.status_code == 400


async def test_record_event_rejects_short_session_id(client: AsyncClient):
    res = await client.post(
        "/events",
        json={"event_type": "view", "product_id": 1, "session_id": "abc"},
    )

    assert res.status_code == 422


# --- GET /recommendations/trending ---

async def test_trending_returns_scored_products(client: AsyncClient):
    res = await client.get("/recommendations/trending", params={"limit": 5})

    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) <= 5
    assert body["strategy"].startswith("trending")
    for item in body["items"]:
        assert item["score"] > 0
        assert "category" in item["product"]


async def test_trending_is_ordered_by_descending_score(client: AsyncClient):
    res = await client.get("/recommendations/trending", params={"limit": 10})

    scores = [i["score"] for i in res.json()["items"]]
    assert scores == sorted(scores, reverse=True)


async def test_trending_rejects_limit_over_cap(client: AsyncClient):
    res = await client.get("/recommendations/trending", params={"limit": 500})

    assert res.status_code == 422


# --- GET /recommendations/similar/{id} ---

async def test_similar_returns_same_category_products(client: AsyncClient):
    product = (await client.get("/products/1")).json()

    res = await client.get(f"/recommendations/similar/{product['id']}", params={"limit": 4})

    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) <= 4
    for item in body["items"]:
        # Same category, and never the product itself.
        assert item["product"]["category"]["id"] == product["category"]["id"]
        assert item["product"]["id"] != product["id"]


async def test_similar_missing_product_returns_404(client: AsyncClient):
    res = await client.get("/recommendations/similar/999999")

    assert res.status_code == 404


async def test_similar_works_for_product_with_no_events(client: AsyncClient):
    """Cold start: the rule-based fallback must not depend on event history."""
    created = await client.post(
        "/products",
        json={
            "name": "Brand New Never Viewed",
            "slug": "pytest-cold-start-item",
            "price": "42.00",
            "stock": 1,
            "category_id": 1,
        },
    )
    assert created.status_code == 201
    new_id = created.json()["id"]

    res = await client.get(f"/recommendations/similar/{new_id}")

    assert res.status_code == 200
    # Zero events, still returns neighbours -- which trending never could.
    assert len(res.json()["items"]) > 0
