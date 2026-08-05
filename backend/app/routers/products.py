"""Product catalog endpoints."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.db import get_session
from app.models import Category, Product
from app.schemas import ProductCreate, ProductList, ProductRead

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductList)
async def list_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    category_id: Annotated[int | None, Query(description="Filter by category id")] = None,
    category_slug: Annotated[
        str | None, Query(description="Filter by category slug, e.g. accessories")
    ] = None,
    min_price: Annotated[
        Decimal | None, Query(ge=0, description="Only products priced at or above")
    ] = None,
    max_price: Annotated[
        Decimal | None, Query(ge=0, description="Only products priced at or below")
    ] = None,
) -> ProductList:
    """List products, oldest id first, paginated, with optional filters."""
    # Filtering on categories.slug means the query must reach the categories
    # table, so we JOIN. An inner join is safe here because category_id is NOT
    # NULL -- every product has one, so no rows are dropped.
    #
    # contains_eager rather than joinedload: we are already joining, so this
    # tells SQLAlchemy to populate Product.category from that same join instead
    # of adding a second one.
    count_stmt = select(func.count()).select_from(Product).join(Product.category)
    stmt = select(Product).join(Product.category).options(contains_eager(Product.category))

    # Each filter is applied to BOTH statements. Applying one only to `stmt`
    # would make `total` count the whole catalog while `items` shows a subset.
    filters = []
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if category_slug is not None:
        filters.append(Category.slug == category_slug)
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    
    for condition in filters:
        count_stmt = count_stmt.where(condition)
        stmt = stmt.where(condition)

    total = await session.scalar(count_stmt)

    result = await session.scalars(
        stmt.order_by(Product.id).limit(limit).offset(offset)
    )

    return ProductList(
        items=list(result),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Product:
    """Fetch one product by id."""
    product = await session.scalar(
        select(Product)
        .options(joinedload(Product.category))
        .where(Product.id == product_id)
    )

    # Returning null with a 200 would tell the client "this succeeded and the
    # product is nothing", which is a lie. 404 is the honest answer.
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Product:
    """Create a product.

    201 rather than 200: the response says a new resource now exists.
    """

    category = await session.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Category {payload.category_id} does not exist",
        )

    product = Product(**payload.model_dump())
    session.add(product)

    try:
        await session.commit()
    except IntegrityError:
        # Raised by the unique index on slug. Without this the client gets a
        # 500 for what is really their mistake.
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"A product with slug '{payload.slug}' already exists",
        ) from None

    # commit() ends the transaction, leaving `product` with no loaded
    # relationship -- so serializing ProductRead.category would raise
    # MissingGreenlet. Re-select it with the category joined in.
    created = await session.scalar(
        select(Product)
        .options(joinedload(Product.category))
        .where(Product.id == product.id)
    )
    assert created is not None  # just committed it; cannot be missing
    return created

   
