"""Registration, login, refresh, logout.

The security decisions of this phase live here: tokens go out as httpOnly
cookies and never in a response body, so no script on the page can read them.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.dependencies import CurrentUser
from app.models import User
from app.rate_limit import client_ip, login_limiter
from app.schemas import AuthResponse, UserCreate, UserLogin, UserRead
from app.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


def _set_auth_cookies(response: Response, user_id: int) -> None:
    """Attach the access and refresh cookies to a response."""
    # Only over HTTPS in production. Left off locally because the dev server is
    # plain http://localhost and the browser would silently drop a Secure cookie.
    secure = settings.environment != "development"

    common = {
        # The whole reason for this design: document.cookie cannot see these,
        # so an XSS payload cannot steal the session.
        "httponly": True,
        "secure": secure,
        # Lax: the browser sends the cookie on normal navigation to this site,
        # but not on a cross-site POST -- which is the CSRF attack. "none"
        # would reopen it, "strict" would break arriving via an external link.
        "samesite": "lax",
    }

    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id),
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(user_id),
        max_age=settings.refresh_token_expire_days * 86400,
        # Scoped, so the long-lived token is only ever transmitted to the one
        # endpoint that needs it, not on every API request.
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    # path must match what was set, or the browser deletes nothing.
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        user=UserRead.model_validate(user),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Create an account and sign the new user in immediately."""
    user = User(
        email=payload.email.lower(),  # so Alice@x.com cannot become a second account
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError:
        # Catching the constraint violation rather than pre-checking with a
        # SELECT: between that check and the insert, another request can claim
        # the address. The unique index is the only real guarantee.
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="An account with that email already exists"
        ) from None

    _set_auth_cookies(response, user.id)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Exchange credentials for auth cookies."""
    # Keyed on IP *and* email: per-IP alone lets a botnet spread one account's
    # guesses across hosts; per-email alone lets anyone lock out a known user.
    key = f"{client_ip(request)}:{payload.email.lower()}"
    login_limiter.check(key)

    result = await session.execute(
        select(User).where(User.email == payload.email.lower())
    )
    user = result.scalar_one_or_none()

    # One message and one status for "no such user" and "wrong password".
    # Distinguishing them turns this endpoint into a way to enumerate which
    # email addresses have accounts here.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    # Only failed attempts should count against the limit, so a person logging
    # in repeatedly on purpose is never locked out.
    login_limiter.reset(key)

    _set_auth_cookies(response, user.id)
    return _auth_response(user)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> AuthResponse:
    """Trade a valid refresh cookie for a fresh pair of cookies.

    expected_type="refresh" is load-bearing: both tokens are signed with the
    same key, so without it a 30-minute access token could be replayed here to
    mint an endless supply of new ones.
    """
    user_id = decode_token(refresh_token or "", expected_type="refresh")
    if user_id is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # Both cookies are reissued, so an active session never has to re-login.
    _set_auth_cookies(response, user.id)
    return _auth_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Clear the cookies.

    Deliberately requires no valid token: logging out must work even from an
    expired session, otherwise the browser keeps a cookie it cannot shed.

    Note what this cannot do -- a JWT already copied elsewhere stays valid until
    it expires. That is the cost of statelessness, and why the access token is
    only 30 minutes. Real revocation needs server-side state (Phase 11).
    """
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> User:
    """Who am I? The protected route the Phase 5 checkpoint exercises.

    `user: CurrentUser` is the entire guard -- no token handling in the body.
    """
    return user
