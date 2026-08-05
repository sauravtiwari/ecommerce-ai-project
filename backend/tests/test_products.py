"""Tests for GET/POST /products.

Reads check against the seeded catalog (Wool Scarf is product id=1, category
Accessories). Writes use the `client` fixture's SAVEPOINT, so nothing here
survives past its own test.
"""

from httpx import AsyncClient


async def test_get_product_returns_seeded_product(client: AsyncClient):
    res = await client.get("/products/1")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == 1
    assert body["name"] == "Wool Scarf"
    assert body["category"]["name"] == "Accessories"


async def test_get_product_missing_returns_404(client: AsyncClient):
    res = await client.get("/products/999999")

    assert res.status_code == 404


async def test_list_products_filters_by_category_and_price(client: AsyncClient):
    res = await client.get(
        "/products", params={"category_slug": "accessories", "min_price": "30"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["total"] > 0
    for item in body["items"]:
        assert item["category"]["slug"] == "accessories"
        assert float(item["price"]) >= 30


async def test_create_product_returns_201(client: AsyncClient):
    payload = {
        "name": "Pytest Test Product",
        "slug": "pytest-test-product",
        "price": "19.99",
        "stock": 5,
        "category_id": 1,
    }

    res = await client.post("/products", json=payload)

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Pytest Test Product"
    assert body["price"] == "19.99"
    assert body["id"] > 0


async def test_create_product_rejects_negative_price(client: AsyncClient):
    payload = {
        "name": "Bad Product",
        "slug": "pytest-bad-price",
        "price": "-5.00",
        "category_id": 1,
    }

    res = await client.post("/products", json=payload)

    assert res.status_code == 422


async def test_create_product_rejects_duplicate_slug(client: AsyncClient):
    # "wool-scarf" already exists in the seeded data.
    payload = {"name": "Duplicate", "slug": "wool-scarf", "price": "10.00", "category_id": 1}

    res = await client.post("/products", json=payload)

    assert res.status_code == 409


async def test_create_product_rejects_missing_category(client: AsyncClient):
    payload = {"name": "Ghost", "slug": "pytest-ghost", "price": "10.00", "category_id": 999999}

    res = await client.post("/products", json=payload)

    assert res.status_code == 400
