"""Game state, day advancement, stock, and export/import endpoints for the Retailer App."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from retailer.database import get_db
from retailer.models import (
    Catalog,
    CustomerOrder,
    RetailerEvent,
    RetailerGameState,
    RetailerMetrics,
    RetailerPurchaseOrder,
    RetailerStock,
)
from retailer.schemas import (
    AdvanceDayResponse,
    DayResponse,
    StockListResponse,
    StockResponse,
)

router = APIRouter()


@router.get("/day/current", response_model=DayResponse)
def get_current_day(db: Session = Depends(get_db)) -> DayResponse:
    """Return current retailer day and wallet balance."""
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")
    return DayResponse(current_day=state.current_day, wallet_balance=state.wallet_balance)


@router.post("/day/advance", response_model=AdvanceDayResponse)
def advance_day(db: Session = Depends(get_db)) -> AdvanceDayResponse:
    """Advance the retailer simulation by one day.

    Steps:
      1. Process delivered purchase orders (add stock)
      2. Auto-fulfill backordered customer orders (FIFO) if stock available
      3. Increment current_day
      4. Commit and log event
      5. Return summary
    """
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")

    current_day = state.current_day
    summary: dict = {
        "deliveries_processed": 0,
        "units_received": 0,
        "backorders_fulfilled": 0,
        "backorder_units_fulfilled": 0,
    }

    # ── 1. Process delivered purchase orders ────────────────────────────────
    delivered_pos = (
        db.query(RetailerPurchaseOrder)
        .filter(
            RetailerPurchaseOrder.status == "delivered",
        )
        .all()
    )
    for po in delivered_pos:
        # Already handled — skip if already received
        # In practice, delivered POs are set by an external process;
        # for now we also auto-deliver POs that have reached their expected day
        pass

    # Auto-deliver pending POs whose expected_delivery_day <= current_day
    pending_pos = (
        db.query(RetailerPurchaseOrder)
        .filter(
            RetailerPurchaseOrder.status == "pending",
            RetailerPurchaseOrder.expected_delivery_day <= current_day,
        )
        .all()
    )
    for po in pending_pos:
        po.status = "delivered"
        po.delivered_day = current_day

        # Add to stock
        stock = db.query(RetailerStock).filter(RetailerStock.model_name == po.model_name).first()
        if stock:
            stock.quantity_on_hand += po.quantity
        else:
            db.add(RetailerStock(model_name=po.model_name, quantity_on_hand=po.quantity))

        # Deduct cost from wallet
        state.wallet_balance -= po.total_price

        summary["deliveries_processed"] += 1
        summary["units_received"] += po.quantity

        db.add(RetailerEvent(
            sim_day=current_day,
            event_type="PURCHASE_ORDER_DELIVERED",
            entity_type="purchase_order",
            entity_id=po.id,
            detail=json.dumps({
                "model_name": po.model_name,
                "quantity": po.quantity,
                "total_price": po.total_price,
            }),
        ))

    # ── 2. Auto-fulfill backordered customer orders (FIFO) ─────────────────
    backordered = (
        db.query(CustomerOrder)
        .filter(CustomerOrder.status == "backordered")
        .order_by(CustomerOrder.order_day.asc(), CustomerOrder.id.asc())
        .all()
    )
    for order in backordered:
        stock = db.query(RetailerStock).filter(RetailerStock.model_name == order.model_name).first()
        if stock and stock.quantity_on_hand >= order.quantity:
            order.status = "fulfilled"
            order.fulfilled_day = current_day
            stock.quantity_on_hand -= order.quantity

            # Revenue
            catalog_item = db.query(Catalog).filter(Catalog.model_name == order.model_name).first()
            if catalog_item:
                revenue = order.quantity * catalog_item.retail_price
                state.wallet_balance += revenue
            else:
                revenue = 0.0

            summary["backorders_fulfilled"] += 1
            summary["backorder_units_fulfilled"] += order.quantity

            db.add(RetailerEvent(
                sim_day=current_day,
                event_type="BACKORDER_FULFILLED",
                entity_type="customer_order",
                entity_id=order.id,
                detail=json.dumps({
                    "model_name": order.model_name,
                    "quantity": order.quantity,
                    "revenue": revenue,
                }),
            ))

    # ── 3. Snapshot metrics before advancing ────────────────────────────────
    stock_snap = {}
    price_snap = {}
    for s in db.query(RetailerStock).all():
        stock_snap[s.model_name] = s.quantity_on_hand
    for c in db.query(Catalog).all():
        price_snap[c.model_name] = c.retail_price

    orders_placed = db.query(CustomerOrder).filter(CustomerOrder.order_day == current_day).count()
    orders_fulfilled = db.query(CustomerOrder).filter(
        CustomerOrder.fulfilled_day == current_day,
        CustomerOrder.status == "fulfilled",
    ).count()
    orders_backordered = db.query(CustomerOrder).filter(
        CustomerOrder.order_day == current_day,
        CustomerOrder.status == "backordered",
    ).count()

    db.add(RetailerMetrics(
        sim_day=current_day,
        printer_stock_json=json.dumps(stock_snap),
        retail_price_json=json.dumps(price_snap),
        customer_orders_placed=orders_placed,
        customer_orders_fulfilled=orders_fulfilled + summary["backorders_fulfilled"],
        customer_orders_backordered=orders_backordered,
        wallet_balance=state.wallet_balance,
    ))

    # ── 4. Increment current_day ───────────────────────────────────────────
    state.current_day += 1

    # ── 5. Log day-advance event and commit ────────────────────────────────
    db.add(RetailerEvent(
        sim_day=state.current_day,
        event_type="DAY_ADVANCED",
        entity_type="game_state",
        entity_id=1,
        detail=json.dumps(summary),
    ))

    db.commit()

    return AdvanceDayResponse(
        success=True,
        new_day=state.current_day,
        wallet_balance=state.wallet_balance,
        summary=summary,
    )


@router.get("/stock", response_model=StockListResponse)
def list_stock(db: Session = Depends(get_db)) -> StockListResponse:
    """List stock per model."""
    items = db.query(RetailerStock).order_by(RetailerStock.id).all()
    return StockListResponse(
        items=[StockResponse.model_validate(item) for item in items],
        count=len(items),
    )


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)) -> list[dict]:
    """Return retailer metrics history for dashboard charts."""
    rows = (
        db.query(RetailerMetrics)
        .order_by(RetailerMetrics.sim_day)
        .all()
    )
    return [
        {
            "sim_day": r.sim_day,
            "wallet_balance": r.wallet_balance,
            "printer_stock_json": r.printer_stock_json,
            "retail_price_json": r.retail_price_json,
            "customer_orders_placed": r.customer_orders_placed,
            "customer_orders_fulfilled": r.customer_orders_fulfilled,
            "customer_orders_backordered": r.customer_orders_backordered,
        }
        for r in rows
    ]


@router.get("/events")
def list_events(
    sim_day: Optional[int] = Query(None, description="Filter events by simulation day"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the last 200 retailer events in chronological order."""
    query = db.query(RetailerEvent)
    if sim_day is not None:
        query = query.filter(RetailerEvent.sim_day == sim_day)
    rows = query.order_by(RetailerEvent.id.desc()).limit(200).all()
    rows.reverse()
    return [
        {
            "id": e.id,
            "sim_day": e.sim_day,
            "event_type": e.event_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "detail": e.detail,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


@router.get("/export")
def export_retailer(db: Session = Depends(get_db)) -> JSONResponse:
    """Export full retailer state as a downloadable JSON snapshot."""
    state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Retailer game state not found")

    catalog = db.query(Catalog).all()
    customer_orders = db.query(CustomerOrder).all()
    purchase_orders = db.query(RetailerPurchaseOrder).all()
    stock = db.query(RetailerStock).all()
    events = db.query(RetailerEvent).all()

    snapshot = {
        "exported_at": datetime.utcnow().isoformat(),
        "game_state": {
            "current_day": state.current_day,
            "wallet_balance": state.wallet_balance,
        },
        "catalog": [
            {
                "id": c.id,
                "model_name": c.model_name,
                "description": c.description,
                "retail_price": c.retail_price,
                "wholesale_price": c.wholesale_price,
            }
            for c in catalog
        ],
        "customer_orders": [
            {
                "id": o.id,
                "customer_name": o.customer_name,
                "model_name": o.model_name,
                "quantity": o.quantity,
                "status": o.status,
                "order_day": o.order_day,
                "fulfilled_day": o.fulfilled_day,
            }
            for o in customer_orders
        ],
        "purchase_orders": [
            {
                "id": po.id,
                "model_name": po.model_name,
                "quantity": po.quantity,
                "status": po.status,
                "ordered_day": po.ordered_day,
                "expected_delivery_day": po.expected_delivery_day,
                "delivered_day": po.delivered_day,
                "unit_price": po.unit_price,
                "total_price": po.total_price,
            }
            for po in purchase_orders
        ],
        "stock": [
            {
                "id": s.id,
                "model_name": s.model_name,
                "quantity_on_hand": s.quantity_on_hand,
            }
            for s in stock
        ],
        "events": [
            {
                "id": e.id,
                "sim_day": e.sim_day,
                "event_type": e.event_type,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "detail": e.detail,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }

    filename = f"retailer_save_day{state.current_day}.json"
    return JSONResponse(
        content=snapshot,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_retailer(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """Import a retailer snapshot, replacing all transactional data."""
    required_keys = {"game_state", "catalog", "customer_orders", "purchase_orders", "stock"}
    if not required_keys.issubset(payload.keys()):
        raise HTTPException(
            status_code=422,
            detail=f"Missing keys: {required_keys - payload.keys()}",
        )

    try:
        # Wipe transactional tables
        db.query(RetailerEvent).delete()
        db.query(CustomerOrder).delete()
        db.query(RetailerPurchaseOrder).delete()
        db.query(RetailerStock).delete()
        db.query(Catalog).delete()

        # Restore game state
        gs_data = payload["game_state"]
        state = db.query(RetailerGameState).filter(RetailerGameState.id == 1).first()
        if state is None:
            raise HTTPException(status_code=404, detail="Retailer game state not found")
        state.current_day = gs_data["current_day"]
        state.wallet_balance = gs_data["wallet_balance"]
        state.last_updated = datetime.utcnow()

        # Restore catalog
        for c_data in payload["catalog"]:
            db.add(Catalog(
                id=c_data["id"],
                model_name=c_data["model_name"],
                description=c_data.get("description"),
                retail_price=c_data["retail_price"],
                wholesale_price=c_data["wholesale_price"],
            ))

        db.flush()

        # Restore customer orders
        for o_data in payload["customer_orders"]:
            db.add(CustomerOrder(
                id=o_data["id"],
                customer_name=o_data["customer_name"],
                model_name=o_data["model_name"],
                quantity=o_data["quantity"],
                status=o_data["status"],
                order_day=o_data["order_day"],
                fulfilled_day=o_data.get("fulfilled_day"),
            ))

        # Restore purchase orders
        for po_data in payload["purchase_orders"]:
            db.add(RetailerPurchaseOrder(
                id=po_data["id"],
                model_name=po_data["model_name"],
                quantity=po_data["quantity"],
                status=po_data["status"],
                ordered_day=po_data["ordered_day"],
                expected_delivery_day=po_data["expected_delivery_day"],
                delivered_day=po_data.get("delivered_day"),
                unit_price=po_data["unit_price"],
                total_price=po_data["total_price"],
            ))

        # Restore stock
        for s_data in payload["stock"]:
            db.add(RetailerStock(
                id=s_data["id"],
                model_name=s_data["model_name"],
                quantity_on_hand=s_data["quantity_on_hand"],
            ))

        # Restore events (optional field)
        for ev_data in payload.get("events", []):
            db.add(RetailerEvent(
                id=ev_data["id"],
                sim_day=ev_data["sim_day"],
                event_type=ev_data["event_type"],
                entity_type=ev_data.get("entity_type"),
                entity_id=ev_data.get("entity_id"),
                detail=ev_data.get("detail"),
                created_at=datetime.fromisoformat(ev_data["created_at"]) if ev_data.get("created_at") else None,
            ))

        db.commit()
        return {"success": True, "message": f"Retailer state imported at day {gs_data['current_day']}"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
