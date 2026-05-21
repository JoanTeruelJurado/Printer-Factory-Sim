"""Catalog API endpoints for the Retailer App."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from retailer.database import get_db
from retailer.models import Catalog
from retailer.schemas import (
    CatalogListResponse,
    CatalogResponse,
    PriceUpdateRequest,
    PriceUpdateResponse,
)

router = APIRouter()


@router.get("/catalog", response_model=CatalogListResponse)
def list_catalog(db: Session = Depends(get_db)) -> CatalogListResponse:
    """List all catalog items with retail prices."""
    items = db.query(Catalog).order_by(Catalog.id).all()
    return CatalogListResponse(
        items=[CatalogResponse.model_validate(item) for item in items],
        count=len(items),
    )


@router.put("/catalog/{model_name}/price", response_model=PriceUpdateResponse)
def update_retail_price(
    model_name: str,
    req: PriceUpdateRequest,
    db: Session = Depends(get_db),
) -> PriceUpdateResponse:
    """Update the retail price for a catalog model."""
    item = db.query(Catalog).filter(Catalog.model_name == model_name).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found in catalog")

    old_price = item.retail_price
    item.retail_price = req.retail_price
    db.commit()
    db.refresh(item)

    return PriceUpdateResponse(
        model_name=item.model_name,
        old_price=old_price,
        new_price=item.retail_price,
    )
