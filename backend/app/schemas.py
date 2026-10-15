"""Pydantic schemas -- the API's wire contract.

Separate from models.py on purpose: those describe how data is stored, these
describe what clients may send and receive. One ORM model, several schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

EventType = Literal["view", "add_to_cart", "purchase"]


class CategoryRead(BaseModel):
    # from_attributes lets Pydantic build this from an ORM object rather than
    # a dict, which is what makes response_model work with SQLAlchemy rows.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    price: Decimal
    stock: int
    is_active: bool
    created_at: datetime
    category: CategoryRead


class ProductCreate(BaseModel):
    """What a client may POST. No id or created_at: the database owns those."""

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=220)
    description: str | None = None
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    category_id: int


class ProductList(BaseModel):
    """Paginated envelope.

    An envelope rather than a bare array: `total` is what pagination controls
    need, and a top-level JSON array can never gain a field without breaking
    every existing client.
    """

    items: list[ProductRead]
    total: int
    limit: int
    offset: int


class EventCreate(BaseModel):
    """One implicit-feedback signal sent by the frontend."""

    # Literal, not str: an unknown event_type is a 422, and it also keeps the
    # API in step with the CHECK constraint on the table.
    event_type: EventType
    product_id: int
    # Generated in the browser and kept in localStorage. Not a secret and not
    # authentication -- just a way to group one visitor's events together
    # before there are accounts.
    session_id: str = Field(min_length=8, max_length=64)


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: EventType
    product_id: int
    session_id: str
    # Echoed back so you can see who the server attributed this to. Never read
    # from the request -- it comes from the auth cookie.
    user_id: int | None = None
    created_at: datetime


class RecommendedProduct(BaseModel):
    """A product plus why it was recommended."""

    product: ProductRead
    # Exposed deliberately: when a rail looks wrong, the first question is
    # always "what did it score?". Hiding it makes every recommender a black
    # box you cannot debug.
    score: float


class RecommendationList(BaseModel):
    items: list[RecommendedProduct]
    # Which algorithm produced this. Phase 10 unions several strategies and
    # Phase 11 requires tracing any live recommendation back to an exact
    # version -- naming it from the start costs nothing.
    strategy: str
    generated_at: datetime


# --- Auth (Phase 5) ---


class UserCreate(BaseModel):
    """A registration request.

    EmailStr rejects malformed addresses before any database work happens --
    validation at the edge, so the endpoint body only ever sees plausible input.
    """

    email: EmailStr
    # 8 is a floor, not a policy. max_length matters more than it looks:
    # bcrypt ignores anything past 72 bytes, and an unbounded password field is
    # a free CPU-exhaustion vector given how slow hashing deliberately is.
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=200)


class UserLogin(BaseModel):
    """A login request. No length rules -- old accounts may predate them."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """A user as the API returns them.

    hashed_password is absent by design. This is why schemas are separate from
    models: the hash cannot leak through an endpoint that forgot to exclude it,
    because there is no field for it to leak into.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """What login and register return.

    No token in the body: the tokens are set as httpOnly cookies, which is the
    entire point of that choice. Returning them here as well would put them
    back within reach of any script on the page.
    """

    user: UserRead
    expires_in: int  # access token lifetime in seconds, so the client can pre-refresh
