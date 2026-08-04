"""Pydantic schemas -- the API's wire contract.

Separate from models.py on purpose: those describe how data is stored, these
describe what clients may send and receive. One ORM model, several schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    # Serialized as the JSON string "29.99". JSON has no decimal type, and
    # emitting a number here would reintroduce the float rounding problem.
    price: Decimal
    stock: int
    is_active: bool
    created_at: datetime
    # Nested, so one request returns the category too. Requires the endpoint
    # to eager-load the relationship -- otherwise N+1.
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
