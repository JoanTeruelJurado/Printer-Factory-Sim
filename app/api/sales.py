"""Sales orders API endpoints — inbound orders from retailers."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import GameState, ManufacturingOrder, SalesOrder
from app.schemas.sales import SalesOrderCreateRequest, SalesOrderResponse
from app.services.sales import (
    create_sales_order,
    get_sales_order,
    list_sales_orders,
    release_sales_order,
    SalesError,
)
from app.services.simulation import log_event

router = APIRouter()


def _order_to_response(order: SalesOrder) -> SalesOrderResponse:
    """Convert a SalesOrder ORM object to a response schema."""
    return SalesOrderResponse(
        id=order.id,
        retailer_name=order.retailer_name,
        product_id=order.product_id,
        product_name=order.product.name,
        quantity=order.quantity,
        status=order.status,
        ordered_day=order.ordered_day,
        released_day=order.released_day,
        completed_day=order.completed_day,
        shipped_day=order.shipped_day,
        delivered_day=order.delivered_day,
        unit_price=order.unit_price,
        total_price=order.total_price,
    )


@router.post("/orders", response_model=SalesOrderResponse)
def create_order(
    req: SalesOrderCreateRequest,
    db: Session = Depends(get_db),
) -> SalesOrderResponse:
    """Accept an inbound order from a retailer."""
    try:
        state = db.query(GameState).filter_by(id=1).first()
        if not state:
            raise HTTPException(status_code=404, detail="Game state not found")

        order = create_sales_order(
            db,
            retailer_name=req.retailer_name,
            product_name=req.model,
            quantity=req.quantity,
            current_day=state.current_day,
        )

        log_event(
            db,
            "SALES_ORDER_CREATED",
            state.current_day,
            "demand",
            {
                "sales_order_id": order.id,
                "retailer_name": order.retailer_name,
                "product_id": order.product_id,
                "quantity": order.quantity,
                "unit_price": order.unit_price,
                "total_price": order.total_price,
            },
        )

        db.commit()
        return _order_to_response(order)
    except SalesError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/orders", response_model=list[SalesOrderResponse])
def list_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[SalesOrderResponse]:
    """List sales orders, optionally filtered by status."""
    orders = list_sales_orders(db, status=status)
    return [_order_to_response(o) for o in orders]


@router.get("/orders/due", response_model=list[SalesOrderResponse])
def list_due_orders(
    day: int,
    db: Session = Depends(get_db),
) -> list[SalesOrderResponse]:
    """List sales orders that are completed or shipped and ready for delivery."""
    orders = (
        db.query(SalesOrder)
        .filter(SalesOrder.status.in_(["completed", "shipped"]))
        .all()
    )
    return [_order_to_response(o) for o in orders]


@router.get("/orders/{order_id}", response_model=SalesOrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> SalesOrderResponse:
    """Get a single sales order."""
    order = get_sales_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return _order_to_response(order)


@router.put("/orders/{order_id}/release", response_model=SalesOrderResponse)
def release_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> SalesOrderResponse:
    """Release a sales order to production (reserves materials)."""
    try:
        order = release_sales_order(db, order_id)

        state = db.query(GameState).filter_by(id=1).first()
        current_day = state.current_day if state else 0

        log_event(
            db,
            "SALES_ORDER_RELEASED",
            current_day,
            "production",
            {
                "sales_order_id": order.id,
                "retailer_name": order.retailer_name,
                "product_id": order.product_id,
                "quantity": order.quantity,
            },
        )

        db.commit()
        return _order_to_response(order)
    except SalesError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/orders/{order_id}/deliver", response_model=SalesOrderResponse)
def deliver_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> SalesOrderResponse:
    """Mark a sales order as delivered (called when retailer acknowledges receipt)."""
    order = get_sales_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if order.status not in ("completed", "shipped"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot deliver order in '{order.status}' status (must be completed or shipped)",
        )

    state = db.query(GameState).filter_by(id=1).first()
    current_day = state.current_day if state else 0

    order.status = "delivered"
    order.delivered_day = current_day

    log_event(
        db,
        "SALES_ORDER_DELIVERED",
        current_day,
        "demand",
        {
            "sales_order_id": order.id,
            "retailer_name": order.retailer_name,
            "product_id": order.product_id,
            "quantity": order.quantity,
            "total_price": order.total_price,
        },
    )

    db.commit()
    return _order_to_response(order)


@router.get("/production/status")
def production_status(
    db: Session = Depends(get_db),
) -> dict:
    """Current production status: released MOs and released sales orders."""
    released_mos = db.query(ManufacturingOrder).filter_by(status="released").all()
    released_sales = db.query(SalesOrder).filter_by(status="released").all()

    return {
        "manufacturing_orders": [
            {
                "id": mo.id,
                "product_id": mo.product_id,
                "product_name": mo.product.name,
                "quantity": mo.quantity,
                "remaining_qty": mo.remaining_qty,
                "status": mo.status,
            }
            for mo in released_mos
        ],
        "sales_orders": [
            {
                "id": so.id,
                "retailer_name": so.retailer_name,
                "product_id": so.product_id,
                "product_name": so.product.name,
                "quantity": so.quantity,
                "status": so.status,
            }
            for so in released_sales
        ],
        "total_released_units": (
            sum(mo.remaining_qty for mo in released_mos)
            + sum(so.quantity for so in released_sales)
        ),
    }


@router.get("/capacity")
def capacity_info(
    db: Session = Depends(get_db),
) -> dict:
    """Daily production capacity and current utilization."""
    state = db.query(GameState).filter_by(id=1).first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found")

    released_mos = db.query(ManufacturingOrder).filter_by(status="released").all()
    released_sales = db.query(SalesOrder).filter_by(status="released").all()

    mo_units = sum(mo.remaining_qty for mo in released_mos)
    sales_units = sum(so.quantity for so in released_sales)

    return {
        "daily_production_capacity": state.daily_production_capacity,
        "released_mo_units": mo_units,
        "released_sales_units": sales_units,
        "total_queued_units": mo_units + sales_units,
        "warehouse_capacity": state.warehouse_capacity,
    }
