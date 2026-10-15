"""A small in-process sliding-window rate limiter.

Honest about its limits: the counters live in this worker's memory, so they
reset on restart and each worker counts separately -- four workers with a limit
of five means twenty attempts. That is fine for slowing a brute-force attack on
a single-process deployment, and wrong for anything that must be exact. Phase 11
introduces Redis, which is where this moves to.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    """Allow `max_attempts` per `window_seconds`, measured from now backwards.

    A sliding window rather than a fixed one: a fixed window resets on the
    clock, so an attacker who waits for the boundary gets 2x the limit in a
    burst across it.
    """

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._hits[key] if now - t < self.window_seconds]
        self._hits[key] = recent
        return recent

    def check(self, key: str) -> None:
        """Record an attempt, or raise 429 if the caller is over the limit."""
        now = time.monotonic()  # immune to NTP jumps and DST, unlike time.time()
        recent = self._prune(key, now)

        if len(recent) >= self.max_attempts:
            retry_after = int(self.window_seconds - (now - recent[0])) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Try again later.",
                # Tells a well-behaved client when to come back instead of
                # leaving it to hammer the endpoint.
                headers={"Retry-After": str(retry_after)},
            )

        self._hits[key].append(now)

    def reset(self, key: str) -> None:
        """Clear a key's history. Called after a successful login."""
        self._hits.pop(key, None)


def client_ip(request: Request) -> str:
    """Best-effort caller identity for rate limiting.

    Behind Render's proxy, request.client.host is the proxy, so every user would
    share one bucket. X-Forwarded-For carries the real chain; the first entry is
    the original client.

    This header is trivially spoofable when the app is exposed directly, which
    is acceptable here -- the cost of a forged header is a bypassed rate limit,
    not a bypassed login. Never use it for anything that grants access.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Five failures per fifteen minutes. Tight enough that online guessing is
# hopeless, loose enough that a person fumbling their own password is not
# locked out. Only failures count -- see the router.
login_limiter = SlidingWindowLimiter(max_attempts=5, window_seconds=15 * 60)
