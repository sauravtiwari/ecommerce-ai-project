"""Auth tests.

Each one asserts a security property, not just a status code -- the comments
say which, because "test_login_works" tells a future reader nothing about what
breaks if it starts failing.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.rate_limit import login_limiter
from app.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    create_access_token,
    decode_token,
)

PASSWORD = "correcthorsebattery"


def unique_email() -> str:
    """A fresh address per test, so tests never collide on the unique index."""
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter is module-global, so without this one test's failed logins
    would count against the next one's budget and fail it at random."""
    login_limiter._hits.clear()
    yield
    login_limiter._hits.clear()


async def register(client: AsyncClient, email: str | None = None, **kw):
    return await client.post(
        "/auth/register",
        json={"email": email or unique_email(), "password": PASSWORD, **kw},
    )


# --- registration ---


@pytest.mark.asyncio
async def test_register_creates_account_and_signs_in(client: AsyncClient):
    email = unique_email()
    r = await register(client, email, full_name="Ada")

    assert r.status_code == 201
    assert r.json()["user"]["email"] == email
    assert r.json()["user"]["full_name"] == "Ada"
    assert ACCESS_COOKIE in r.cookies  # registering logs you straight in


@pytest.mark.asyncio
async def test_register_never_returns_the_password_or_its_hash(client: AsyncClient):
    """The hash must not reach the client, in any field, ever."""
    r = await register(client)
    body = r.text
    assert PASSWORD not in body
    assert "hashed_password" not in body
    assert "$2b$" not in body  # the bcrypt prefix


@pytest.mark.asyncio
async def test_tokens_are_httponly_and_not_in_the_body(client: AsyncClient):
    """The whole point of the cookie design: script cannot read the token."""
    r = await register(client)

    assert "access_token" not in r.json()  # not in the JSON body
    cookies = r.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith(f"{ACCESS_COOKIE}="))
    refresh = next(c for c in cookies if c.startswith(f"{REFRESH_COOKIE}="))

    assert "HttpOnly" in access  # blocks document.cookie, i.e. XSS theft
    assert "samesite=lax" in access.lower()  # blocks cross-site POSTs, i.e. CSRF
    # The long-lived token is scoped so it is not sent on every request.
    assert "Path=/auth/refresh" in refresh


@pytest.mark.asyncio
async def test_duplicate_email_is_rejected(client: AsyncClient):
    email = unique_email()
    assert (await register(client, email)).status_code == 201
    assert (await register(client, email)).status_code == 409


@pytest.mark.asyncio
async def test_email_is_normalised_to_lowercase(client: AsyncClient):
    """Otherwise Ada@x.com and ada@x.com become two accounts."""
    email = unique_email()
    r = await register(client, email.upper())
    assert r.json()["user"]["email"] == email.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@b.com", "password": "short"},  # under the 8-char floor
        {"email": "a@b.com", "password": "x" * 73},  # past bcrypt's 72-byte limit
        {"email": "a@b.com"},  # missing entirely
    ],
)
@pytest.mark.asyncio
async def test_bad_payloads_are_422_not_500(client: AsyncClient, payload):
    """Malformed input is a client error. A 500 here would mean the validation
    boundary leaked and something downstream crashed on unchecked data."""
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 422


# --- login ---


@pytest.mark.asyncio
async def test_login_with_correct_password(client: AsyncClient):
    email = unique_email()
    await register(client, email)
    client.cookies.clear()

    r = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    assert ACCESS_COOKIE in r.cookies


@pytest.mark.asyncio
async def test_wrong_password_and_unknown_user_are_indistinguishable(
    client: AsyncClient,
):
    """Different responses would let anyone enumerate which emails have accounts."""
    email = unique_email()
    await register(client, email)

    wrong = await client.post(
        "/auth/login", json={"email": email, "password": "not-the-password"}
    )
    missing = await client.post(
        "/auth/login", json={"email": unique_email(), "password": PASSWORD}
    )

    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["detail"] == missing.json()["detail"]


@pytest.mark.asyncio
async def test_failed_logins_are_rate_limited(client: AsyncClient):
    """Brute-force protection: five failures, then the door shuts."""
    email = unique_email()
    await register(client, email)

    codes = [
        (
            await client.post("/auth/login", json={"email": email, "password": f"g{i}"})
        ).status_code
        for i in range(6)
    ]

    assert codes[:5] == [401] * 5
    assert codes[5] == 429


@pytest.mark.asyncio
async def test_successful_login_clears_the_failure_count(client: AsyncClient):
    """Someone fumbling their own password must not lock themselves out."""
    email = unique_email()
    await register(client, email)

    for i in range(4):
        await client.post("/auth/login", json={"email": email, "password": f"g{i}"})
    assert (
        await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200

    # The budget is back: a fresh failure is a 401, not an immediate 429.
    r = await client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401


# --- protected routes ---


@pytest.mark.asyncio
async def test_protected_route_rejects_anonymous(client: AsyncClient):
    r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_accepts_signed_in_user(client: AsyncClient):
    email = unique_email()
    await register(client, email)

    r = await client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == email


@pytest.mark.parametrize("bad_token", ["garbage", "a.b.c"])
@pytest.mark.asyncio
async def test_malformed_token_is_rejected(client: AsyncClient, bad_token):
    client.cookies.set(ACCESS_COOKIE, bad_token)
    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_tampered_signature_is_rejected(client: AsyncClient):
    """Flipping one character of a real token must invalidate it -- this is
    what stops anyone editing the readable `sub` claim to impersonate a user."""
    await register(client)
    token = client.cookies[ACCESS_COOKIE]
    client.cookies.set(ACCESS_COOKIE, token[:-1] + ("A" if token[-1] != "A" else "B"))

    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_token_for_a_nonexistent_user_is_rejected(client: AsyncClient):
    """A perfectly signed token is still not enough -- the account must exist.
    This DB lookup is the only thing that makes a stateless JWT revocable."""
    client.cookies.set(ACCESS_COOKIE, create_access_token(999_999_999))
    assert (await client.get("/auth/me")).status_code == 401


# --- logout and refresh ---


@pytest.mark.asyncio
async def test_logout_then_protected_route_is_rejected(client: AsyncClient):
    """The Phase 5 checkpoint, in one test."""
    email = unique_email()
    await register(client, email)
    assert (await client.get("/auth/me")).status_code == 200

    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.get("/auth/me")).status_code == 401

    await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert (await client.get("/auth/me")).status_code == 200


@pytest.mark.asyncio
async def test_refresh_issues_a_new_access_token(client: AsyncClient):
    await register(client)
    original = client.cookies[ACCESS_COOKIE]

    r = await client.post("/auth/refresh")
    assert r.status_code == 200
    # A genuine token came back: it survives the same checks /auth/me applies.
    assert decode_token(client.cookies[ACCESS_COOKIE], "access") is not None
    assert (await client.get("/auth/me")).status_code == 200
    # Not asserting the string differs from `original`: minted in the same
    # second, the payload is byte-identical, so that would flake.
    assert decode_token(original, "access") is not None


@pytest.mark.asyncio
async def test_access_token_cannot_be_used_to_refresh(client: AsyncClient):
    """The `type` claim doing its job. Both tokens share a signing key, so
    without it a 30-minute token could be replayed here for a 7-day one."""
    await register(client)
    client.cookies.set(REFRESH_COOKIE, client.cookies[ACCESS_COOKIE])

    assert (await client.post("/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_a_cookie_is_rejected(client: AsyncClient):
    assert (await client.post("/auth/refresh")).status_code == 401


# --- events attribution ---


@pytest.mark.asyncio
async def test_events_are_anonymous_when_logged_out(client: AsyncClient):
    product_id = (await client.get("/products?limit=1")).json()["items"][0]["id"]

    r = await client.post(
        "/events",
        json={
            "event_type": "view",
            "product_id": product_id,
            "session_id": "anon-session-1",
        },
    )
    assert r.status_code == 201
    assert r.json()["user_id"] is None


@pytest.mark.asyncio
async def test_events_are_attributed_to_the_signed_in_user(client: AsyncClient):
    r = await register(client)
    user_id = r.json()["user"]["id"]
    product_id = (await client.get("/products?limit=1")).json()["items"][0]["id"]

    r = await client.post(
        "/events",
        json={
            "event_type": "view",
            "product_id": product_id,
            "session_id": "signed-in-1",
            # Sent deliberately: the client must not be able to choose this.
            "user_id": 999_999,
        },
    )
    assert r.status_code == 201
    # Taken from the verified cookie, not the body -- nobody can log events
    # as somebody else.
    assert r.json()["user_id"] == user_id
