"""Customer order API endpoints for the Retailer App."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from retailer.database import get_db
from retailer.models import (
    Catalog,
    CustomerOrder,
    RetailerEvent,
    RetailerGameState,
    RetailerStock,
)
from retailer.schemas import (
    CustomerOrderListResponse,
    CustomerOrderRequest,
    CustomerOrderResponse,
)

router = APIRouter()


@router.post("/orders", response_model=CustomerOrderResponse)
def create_customer_order(
    req: CustomerOrderRequest,
    db: Session = Depends(get_db),
) -> CustomerOrderResponse:
    """Create a customer order.

    If stock is available the order is auto-fulfilled immediately;
    otherwise it is marked as backordered.
    """
    # 1. Validate model exists in catalog
    catalog_item = db.query(Catalog).filter(Catalog.model_name == req.model).first()
    if catalog_item is None:
        raise HTTPException(status_code=404, detail=f"Model '{req.model}' not found in catalog")

    # 2. Get current game state day
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")

    current_day = state.current_day

    # 3. Create CustomerOrder with status="pending"
    order = CustomerOrder(
        customer_name=req.customer_name,
        model_name=req.model,
        quantity=req.quantity,
        status="pending",
        order_day=current_day,
    )
    db.add(order)
    db.flush()  # get the order ID

    # 4. Check stock and auto-fulfill or backorder
    stock = db.query(RetailerStock).filter(RetailerStock.model_name == req.model).first()
    stock_qty = stock.quantity_on_hand if stock else 0

    if stock_qty >= req.quantity:
        # Auto-fulfill
        order.status = "fulfilled"
        order.fulfilled_day = current_day
        stock.quantity_on_hand -= req.quantity

        # Add revenue to wallet
        revenue = req.quantity * catalog_item.retail_price
        state.wallet_balance += revenue

        # Log event
        db.add(RetailerEvent(
            sim_day=current_day,
            event_type="ORDER_FULFILLED",
            entity_type="customer_order",
            entity_id=order.id,
            detail=json.dumps({
                "customer_name": req.customer_name,
                "model_name": req.model,
                "quantity": req.quantity,
                "revenue": revenue,
                "auto_fulfilled": True,
            }),
        ))
    else:
        # Backorder
        order.status = "backordered"
        db.add(RetailerEvent(
            sim_day=current_day,
            event_type="ORDER_BACKORDERED",
            entity_type="customer_order",
            entity_id=order.id,
            detail=json.dumps({
                "customer_name": req.customer_name,
                "model_name": req.model,
                "quantity": req.quantity,
                "stock_available": stock_qty,
            }),
        ))

    db.commit()
    db.refresh(order)

    return CustomerOrderResponse.model_validate(order)


@router.get("/orders", response_model=CustomerOrderListResponse)
def list_customer_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> CustomerOrderListResponse:
    """List customer orders, optionally filtered by status."""
    query = db.query(CustomerOrder)
    if status:
        query = query.filter(CustomerOrder.status == status)
    orders = query.order_by(CustomerOrder.id.desc()).all()
    return CustomerOrderListResponse(
        orders=[CustomerOrderResponse.model_validate(o) for o in orders],
        count=len(orders),
    )


@router.get("/orders/{order_id}", response_model=CustomerOrderResponse)
def get_customer_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> CustomerOrderResponse:
    """Get a single customer order by ID."""
    order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Customer order {order_id} not found")
    return CustomerOrderResponse.model_validate(order)


@router.post("/orders/{order_id}/fulfill", response_model=CustomerOrderResponse)
def fulfill_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> CustomerOrderResponse:
    """Manually fulfill a customer order from stock.

    Decrements stock, sets status to fulfilled, adds revenue to wallet,
    and logs an event. Returns 400 if not enough stock.
    """
    order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Customer order {order_id} not found")

    if order.status == "fulfilled":
        raise HTTPException(status_code=400, detail="Order is already fulfilled")
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot fulfill a cancelled order")

    # Check stock
    stock = db.query(RetailerStock).filter(RetailerStock.model_name == order.model_name).first()
    stock_qty = stock.quantity_on_hand if stock else 0

    if stock_qty < order.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough stock: need {order.quantity}, have {stock_qty}",
        )

    # Decrement stock
    stock.quantity_on_hand -= order.quantity

    # Get game state and catalog for revenue
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")

    catalog_item = db.query(Catalog).filter(Catalog.model_name == order.model_name).first()
    revenue = order.quantity * catalog_item.retail_price if catalog_item else 0.0

    # Update order
    order.status = "fulfilled"
    order.fulfilled_day = state.current_day

    # Add revenue to wallet
    state.wallet_balance += revenue

    # Log event
    db.add(RetailerEvent(
        sim_day=state.current_day,
        event_type="ORDER_FULFILLED",
        entity_type="customer_order",
        entity_id=order.id,
        detail=json.dumps({
            "customer_name": order.customer_name,
            "model_name": order.model_name,
            "quantity": order.quantity,
            "revenue": revenue,
            "auto_fulfilled": False,
        }),
    ))

    db.commit()
    db.refresh(order)

    return CustomerOrderResponse.model_validate(order)


@router.post("/orders/{order_id}/backorder", response_model=CustomerOrderResponse)
def backorder_order(
    order_id: int,
    db: Session = Depends(get_db),
) -> CustomerOrderResponse:
    """Mark a pending customer order as backordered."""
    order = db.query(CustomerOrder).filter(CustomerOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Customer order {order_id} not found")

    if order.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Only pending orders can be backordered (current status: {order.status})",
        )

    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    current_day = state.current_day if state else 0

    order.status = "backordered"

    db.add(RetailerEvent(
        sim_day=current_day,
        event_type="ORDER_BACKORDERED",
        entity_type="customer_order",
        entity_id=order.id,
        detail=json.dumps({
            "customer_name": order.customer_name,
            "model_name": order.model_name,
            "quantity": order.quantity,
        }),
    ))

    db.commit()
    db.refresh(order)

    return CustomerOrderResponse.model_validate(order)
