"""Manufacturing orders API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import GameState, ManufacturingOrder
from app.schemas.manufacturing import (
    ManufacturingOrderResponse,
    CreateManufacturingOrderRequest,
    ReleaseManufacturingOrderRequest,
)
from app.services.production import (
    create_manufacturing_order,
    release_manufacturing_order,
    cancel_manufacturing_order,
    get_order_requirements,
    ProductionError,
)

router = APIRouter()


@router.get("/manufacturing-orders", response_model=list[ManufacturingOrderResponse])
def list_manufacturing_orders(db: Session = Depends(get_db)) -> list[ManufacturingOrderResponse]:
    """List all manufacturing orders."""
    orders = db.query(ManufacturingOrder).all()
    result = []
    for order in orders:
        req = get_order_requirements(db, order.id)
        result.append(ManufacturingOrderResponse(**req))
    return result


@router.post("/manufacturing-orders", response_model=ManufacturingOrderResponse)
def create_order(
    req: CreateManufacturingOrderRequest,
    db: Session = Depends(get_db),
) -> ManufacturingOrderResponse:
    """Create a new manufacturing order."""
    try:
        game_state = db.query(GameState).filter_by(id=1).first()
        if not game_state:
            raise HTTPException(status_code=404, detail="Game state not found")
        
        order = create_manufacturing_order(db, req.product_id, req.quantity, game_state.current_day)
        db.commit()
        
        order_req = get_order_requirements(db, order.id)
        return ManufacturingOrderResponse(**order_req)
    except ProductionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/manufacturing-orders/{order_id}", response_model=ManufacturingOrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)) -> ManufacturingOrderResponse:
    """Get a specific manufacturing order."""
    try:
        order = db.query(ManufacturingOrder).filter_by(id=order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        req = get_order_requirements(db, order_id)
        return ManufacturingOrderResponse(**req)
    except ProductionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/manufacturing-orders/{order_id}/release", response_model=ManufacturingOrderResponse)
def release_order(
    order_id: int,
    req: ReleaseManufacturingOrderRequest,
    db: Session = Depends(get_db),
) -> ManufacturingOrderResponse:
    """Release a manufacturing order to production."""
    try:
        order = release_manufacturing_order(db, order_id, req.quantity)
        db.commit()
        
        order_req = get_order_requirements(db, order.id)
        return ManufacturingOrderResponse(**order_req)
    except ProductionError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/manufacturing-orders/{order_id}/cancel", response_model=dict)
def cancel_order(order_id: int, db: Session = Depends(get_db)) -> dict:
    """Cancel a manufacturing order."""
    try:
        order = cancel_manufacturing_order(db, order_id)
        db.commit()
        
        return {
            "success": True,
            "message": f"Order {order_id} cancelled",
            "order_id": order_id,
            "status": order.status,
        }
    except ProductionError as e:
        raise HTTPException(status_code=422, detail=str(e))
