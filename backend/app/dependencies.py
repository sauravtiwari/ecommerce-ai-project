"""Auth dependencies -- the bridge between a cookie and a User row.

Written as FastAPI dependencies so protecting a route is one parameter, and so
the check cannot be forgotten halfway down an endpoint body.
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import ACCESS_COOKIE, decode_token

# 401 says "I don't know who you are"; 403 would say "I know, and no".
# WWW-Authenticate is what the 401 spec requires alongside it.
_UNAUTHENTICATED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    # Read straight from the cookie the browser attached. alias= is needed
    # because the cookie's name is not a valid Python identifier pattern here.
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User | None:
    """The signed-in user, or None. Never raises.

    For endpoints that serve everyone but do something extra when signed in --
    /events attributing a view to an account rather than a browser.
    """
    if access_token is None:
        return None

    user_id = decode_token(access_token, expected_type="access")
    if user_id is None:
        return None

    user = await session.get(User, user_id)
    # A valid signature is not enough: the account may have been deleted or
    # disabled since the token was minted, and a stateless JWT cannot know that.
    # This DB lookup is what makes revocation possible at all.
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """The signed-in user, or 401. Add this to any route that requires login."""
    if user is None:
        raise _UNAUTHENTICATED
    return user


# Read as "a User, provided by get_current_user". Endpoints annotate with this
# instead of repeating the Depends() spelling.
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
