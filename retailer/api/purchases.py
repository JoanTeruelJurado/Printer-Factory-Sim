"""Purchase order API endpoints for the Retailer App.

Purchase orders are placed by the retailer with the manufacturer
to replenish stock of finished printers.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from retailer.database import get_db
from retailer.models import (
    Catalog,
    RetailerEvent,
    RetailerGameState,
    RetailerPurchaseOrder,
)
from retailer.schemas import (
    PurchaseCreateRequest,
    PurchaseListResponse,
    PurchaseResponse,
)

DEFAULT_LEAD_TIME = 3

router = APIRouter()


@router.post("/purchases", response_model=PurchaseResponse)
def create_purchase_order(
    req: PurchaseCreateRequest,
    db: Session = Depends(get_db),
) -> PurchaseResponse:
    """Create a purchase order with the manufacturer.

    For now the order is recorded locally since the manufacturer
    endpoint may not exist yet. Uses wholesale_price from catalog
    and a default lead time of 3 days.
    """
    # 1. Validate model exists in catalog
    catalog_item = db.query(Catalog).filter(Catalog.model_name == req.model).first()
    if catalog_item is None:
        raise HTTPException(status_code=404, detail=f"Model '{req.model}' not found in catalog")

    # 2. Get current game state
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")

    current_day = state.current_day
    unit_price = catalog_item.wholesale_price
    total_price = unit_price * req.quantity

    # 3. Create the RetailerPurchaseOrder locally
    po = RetailerPurchaseOrder(
        model_name=req.model,
        quantity=req.quantity,
        status="pending",
        ordered_day=current_day,
        expected_delivery_day=current_day + DEFAULT_LEAD_TIME,
        unit_price=unit_price,
        total_price=total_price,
    )
    db.add(po)
    db.flush()

    # 4. Try to call manufacturer API (best effort)
    try:
        import httpx

        from retailer.config import load_retailer_config

        cfg = load_retailer_config()
        manufacturer_url = cfg.get("retailer", {}).get("manufacturer", {}).get("url", "http://localhost:8002")
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{manufacturer_url}/api/orders",
                json={
                    "retailer_name": cfg.get("retailer", {}).get("name", "PrinterWorld"),
                    "model": req.model,
                    "quantity": req.quantity,
                },
            )
    except Exception:
        pass  # Manufacturer may not be running; order is recorded locally

    # 5. Log event
    db.add(RetailerEvent(
        sim_day=current_day,
        event_type="PURCHASE_ORDER_CREATED",
        entity_type="purchase_order",
        entity_id=po.id,
        detail=json.dumps({
            "model_name": req.model,
            "quantity": req.quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "expected_delivery_day": po.expected_delivery_day,
        }),
    ))

    db.commit()
    db.refresh(po)

    return PurchaseResponse.model_validate(po)


@router.get("/purchases", response_model=PurchaseListResponse)
def list_purchase_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> PurchaseListResponse:
    """List purchase orders, optionally filtered by status."""
    query = db.query(RetailerPurchaseOrder)
    if status:
        query = query.filter(RetailerPurchaseOrder.status == status)
    orders = query.order_by(RetailerPurchaseOrder.id.desc()).all()
    return PurchaseListResponse(
        orders=[PurchaseResponse.model_validate(o) for o in orders],
        count=len(orders),
    )
