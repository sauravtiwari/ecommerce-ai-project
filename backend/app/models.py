"""SQLAlchemy ORM models. Alembic reads Base.metadata to generate migrations."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class Category(Base):
    """A product category. Owns its own name and description (3NF)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    """A sellable item, belonging to exactly one category."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Numeric, never Float: binary floats cannot represent decimal money exactly.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Postgres does not index foreign keys automatically, and every catalog
    # filter and join uses this column.
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="products")
    events: Mapped[list["Event"]] = relationship(back_populates="product")


class Event(Base):
    """One implicit-feedback signal: somebody viewed or carted a product.

    This table only ever grows, and every recommender from Phase 4 onward reads
    from it. Rows are facts about the past, so nothing here is ever updated.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    # There is no users table until Phase 5, so visitors are identified by an
    # anonymous id the browser generates and keeps in localStorage. Real
    # analytics works this way too -- most traffic is logged out. Phase 5 adds
    # a nullable user_id beside this via its own migration.
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="events")

    __table_args__ = (
        # The database refuses a bad event_type even if a bug bypasses Pydantic.
        # Validation at the edge is convenience; a constraint here is a
        # guarantee.
        CheckConstraint(
            "event_type IN ('view', 'add_to_cart', 'purchase')",
            name="ck_events_event_type",
        ),
        # The trending query filters by time and groups by product, so the
        # composite index covers it in one structure.
        Index("ix_events_created_at_product", "created_at", "product_id"),
    )
