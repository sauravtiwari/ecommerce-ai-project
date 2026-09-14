"""Implicit-feedback collection."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Event, Product
from app.schemas import EventCreate, EventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def record_event(
    payload: EventCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Event:
    """Record a view / add_to_cart / purchase.

    Called on nearly every page view, so it stays deliberately cheap: one
    existence check and one insert, no joins, nothing returned that the caller
    has to wait for.
    """
    # Without this the foreign key raises IntegrityError and the client gets a
    # 500 for what is really a bad request.
    if await session.get(Product, payload.product_id) is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Product {payload.product_id} does not exist",
        )

    event = Event(**payload.model_dump())
    session.add(event)
    await session.commit()
    # Events have no relationships to serialize, so unlike create_product this
    # needs no re-select -- expire_on_commit=False leaves the attributes
    # readable.
    return event
