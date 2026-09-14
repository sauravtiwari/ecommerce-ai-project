"""Recommendation endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Product
from app.recommenders import similar_products_statement, trending_statement
from app.schemas import ProductRead, RecommendationList, RecommendedProduct

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _to_response(rows, strategy: str) -> RecommendationList:
    """Rows of (Product, score) -> the API response."""
    return RecommendationList(
        items=[
            RecommendedProduct(product=ProductRead.model_validate(p), score=float(s))
            for p, s in rows
        ],
        strategy=strategy,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/trending", response_model=RecommendationList)
async def trending(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    half_life_hours: Annotated[
        float, Query(gt=0, le=8760, description="Hours for an event's weight to halve")
    ] = 24.0,
) -> RecommendationList:
    """Most popular products right now, weighted by signal and decayed by age.

    half_life_hours is exposed as a query parameter so you can see the ranking
    change: a small value is "what is hot in the last few hours", a large one
    converges on all-time popularity.
    """
    stmt = trending_statement(
        now=datetime.now(timezone.utc),
        limit=limit,
        half_life_hours=half_life_hours,
    )
    rows = (await session.execute(stmt)).unique().all()
    return _to_response(rows, strategy=f"trending:half_life={half_life_hours}h")


@router.get("/similar/{product_id}", response_model=RecommendationList)
async def similar(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RecommendationList:
    """Same-category products at a similar price. Needs no event history."""
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    stmt = similar_products_statement(product=product, limit=limit)
    rows = (await session.execute(stmt)).unique().all()
    return _to_response(rows, strategy="similar:same-category-nearest-price")
