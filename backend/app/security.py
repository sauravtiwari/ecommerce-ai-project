"""Password hashing and JWT minting.

Deliberately knows nothing about FastAPI, HTTP, or the database -- it turns
strings into other strings. That makes every rule in here testable without
standing up an app, and keeps the crypto in one auditable place.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]

# Cookie names, shared by the router that sets them and the dependency that
# reads them. One definition, so a rename cannot desynchronise the two.
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
# The refresh cookie is scoped to this path, so the browser attaches it to
# exactly one endpoint instead of every API call.
REFRESH_COOKIE_PATH = "/auth/refresh"

# bcrypt hashes at most 72 bytes and silently ignores the rest, so without a
# check "correct-horse...<72 bytes>...A" and "...B" are the same password.
# Bytes, not characters: one emoji is 4 of these.
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a password for storage. Never store the return value's input."""
    pw = plain_password.encode("utf-8")
    if len(pw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password exceeds {MAX_PASSWORD_BYTES} bytes")
    # gensalt() embeds a random salt in the output, so two people sharing a
    # password get different hashes and one rainbow table cannot cover both.
    # Its work factor is what makes this deliberately slow to brute-force.
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against a stored hash.

    checkpw compares in constant time: a plain `==` leaks how much of the hash
    matched through how long it took to say no.
    """
    pw = plain_password.encode("utf-8")
    if len(pw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))
    except ValueError:
        # A malformed hash in the database is a failed login, not a 500.
        return False


def _create_token(subject: str | int, token_type: TokenType, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),  # the JWT spec requires `sub` to be a string
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str | int) -> str:
    """Short-lived token proving who the caller is. Sent on every request."""
    return _create_token(
        user_id, "access", timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: str | int) -> str:
    """Long-lived token whose only power is minting a new access token."""
    return _create_token(
        user_id, "refresh", timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: TokenType) -> int | None:
    """Return the user id in a valid token, or None.

    expected_type is the point of this function. Both tokens are signed with
    the same key, so without checking the claim a 7-day refresh token would be
    accepted as an access token -- handing an attacker a week instead of half
    an hour.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            # A list, and never including "none": the classic JWT attack is
            # re-signing a token with alg=none and having the server trust it.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        # Covers expiry, a bad signature, and malformed input alike. The caller
        # gets 401 for all of them -- distinguishing them tells an attacker
        # which part of their forgery to fix.
        return None

    if payload.get("type") != expected_type:
        return None

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
