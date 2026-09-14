"""Pydantic schemas -- the API's wire contract.

Separate from models.py on purpose: those describe how data is stored, these
describe what clients may send and receive. One ORM model, several schemas.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
