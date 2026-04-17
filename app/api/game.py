from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Config, DemandOrder, Event, GameState, Inventory, ManufacturingOrder, Product
from app.schemas import GameStateResponse, InventoryItemResponse
from app.services.seed import reset_game
from app.services.simulation import advance_day, SimulationError

router = APIRouter()


@router.get("/state", response_model=GameStateResponse)
def get_game_state(db: Session = Depends(get_db)) -> GameStateResponse:
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")

    warehouse_used = db.query(Inventory).with_entities(
        (Inventory.quantity + Inventory.reserved_quantity).label("used")
    ).all()
    total_used = sum(row.used for row in warehouse_used)

    warning_level = None
    capacity_threshold = db.query(Config).filter(Config.key == "capacity_warning_threshold").first()
    if capacity_threshold:
        try:
            threshold = float(capacity_threshold.value)
            if total_used >= state.warehouse_capacity * threshold:
                warning_level = "capacity"
        except ValueError:
            pass

    return GameStateResponse(
        current_day=state.current_day,
        wallet_balance=state.wallet_balance,
        warehouse_capacity=state.warehouse_capacity,
        warehouse_used=total_used,
        daily_production_capacity=state.daily_production_capacity,
        production_used_today=0,
        game_over=state.game_over,
        warning_level=warning_level,
    )


@router.get("/inventory", response_model=list[InventoryItemResponse])
def list_inventory(db: Session = Depends(get_db)) -> list[InventoryItemResponse]:
    inventory_rows = db.query(Inventory).join(Inventory.material).all()
    result: list[InventoryItemResponse] = []
    for item in inventory_rows:
        result.append(
            InventoryItemResponse(
                material_id=item.material_id,
                material_name=item.material.name,
                quantity=item.quantity,
                reserved_quantity=item.reserved_quantity,
                volume_per_unit=item.material.volume_per_unit,
                total_volume=item.quantity * item.material.volume_per_unit,
            )
        )
    return result


@router.post("/reset")
def reset_game_state(db: Session = Depends(get_db)) -> dict:
    reset_game(db)
    return {"success": True, "message": "Game reset to initial state."}


@router.get("/demand-orders")
def list_demand_orders(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    """List demand orders, optionally filtered by status."""
    query = db.query(DemandOrder)
    if status:
        query = query.filter(DemandOrder.status == status)
    orders = query.order_by(DemandOrder.id.desc()).all()
    return [
        {
            "demand_id": o.id,
            "product_id": o.product_id,
            "product_name": o.product.name,
            "quantity": o.quantity,
            "fulfilled_qty": o.fulfilled_qty,
            "request_day": o.request_day,
            "due_day": o.due_day,
            "status": o.status,
            "penalty_amount": o.penalty_amount,
        }
        for o in orders
    ]


@router.get("/products")
def list_products(db: Session = Depends(get_db)) -> list[dict]:
    """List all active finished products."""
    products = (
        db.query(Product)
        .filter(Product.product_type == "finished", Product.status == "active")
        .all()
    )
    return [
        {
            "product_id": p.id,
            "product_name": p.name,
            "sell_price": p.sell_price,
            "assembly_time_hours": p.assembly_time_hours,
        }
        for p in products
    ]


@router.get("/events")
def list_events(
    category: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List simulation events, optionally filtered by category."""
    query = db.query(Event)
    if category and category != "all":
        query = query.filter(Event.category == category)
    events = query.order_by(Event.id.desc()).limit(limit).all()
    return [
        {
            "event_id": e.id,
            "event_type": e.event_type,
            "sim_day": e.sim_day,
            "category": e.category,
            "details": e.details,
            "timestamp": str(e.timestamp),
        }
        for e in events
    ]


@router.get("/finished-goods")
def get_finished_goods(db: Session = Depends(get_db)) -> dict:
    """Return available finished goods per product (completed MO qty minus fulfilled demand qty)."""
    completed_mos = db.query(ManufacturingOrder).filter(ManufacturingOrder.status == "completed").all()
    produced: dict[int, int] = {}
    for mo in completed_mos:
        produced[mo.product_id] = produced.get(mo.product_id, 0) + mo.quantity

    # Subtract already fulfilled demand
    fulfilled_demands = db.query(DemandOrder).filter(
        DemandOrder.status.in_(["fulfilled", "partial"])
    ).all()
    for d in fulfilled_demands:
        if d.product_id in produced:
            produced[d.product_id] = max(0, produced[d.product_id] - d.fulfilled_qty)

    return produced


@router.post("/demand-orders/{demand_id}/fulfill")
def fulfill_demand_manually(demand_id: int, db: Session = Depends(get_db)) -> dict:
    """Manually fulfill a demand order. Revenue only if served on or before due date."""
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")

    demand = db.query(DemandOrder).filter(DemandOrder.id == demand_id).first()
    if demand is None:
        raise HTTPException(status_code=404, detail="Demand order not found")

    if demand.status not in ("open", "partial"):
        raise HTTPException(status_code=400, detail=f"Order is already {demand.status}")

    # Check finished goods availability
    completed_mos = db.query(ManufacturingOrder).filter(
        ManufacturingOrder.status == "completed",
        ManufacturingOrder.product_id == demand.product_id,
    ).all()
    produced = sum(mo.quantity for mo in completed_mos)

    other_fulfilled = db.query(DemandOrder).filter(
        DemandOrder.status.in_(["fulfilled", "partial"]),
        DemandOrder.id != demand_id,
        DemandOrder.product_id == demand.product_id,
    ).all()
    already_used = sum(d.fulfilled_qty for d in other_fulfilled)

    available = max(0, produced - already_used)
    needed = demand.quantity - demand.fulfilled_qty

    if available <= 0:
        raise HTTPException(status_code=422, detail="No finished goods available for this product")

    qty_to_serve = min(needed, available)
    demand.fulfilled_qty += qty_to_serve

    on_time = state.current_day <= demand.due_day
    revenue = 0.0
    if on_time:
        revenue = qty_to_serve * demand.product.sell_price
        state.wallet_balance += revenue

    if demand.fulfilled_qty >= demand.quantity:
        demand.status = "fulfilled"
    else:
        demand.status = "partial"

    from app.services.simulation import log_event
    log_event(
        db,
        "DEMAND_FULFILLED" if on_time else "DEMAND_SERVED_LATE",
        state.current_day,
        "demand",
        {
            "demand_id": demand.id,
            "product_id": demand.product_id,
            "qty_served": qty_to_serve,
            "on_time": on_time,
            "revenue": revenue,
        },
    )

    db.commit()
    return {
        "success": True,
        "qty_served": qty_to_serve,
        "on_time": on_time,
        "revenue": revenue,
        "new_status": demand.status,
    }


@router.post("/advance-day")
def advance_day_endpoint(db: Session = Depends(get_db)) -> dict:
    """Advance simulation by one day."""
    try:
        state = db.query(GameState).filter(GameState.id == 1).first()
        if state is None:
            raise HTTPException(status_code=404, detail="Game state not found")
        
        if state.game_over:
            raise HTTPException(status_code=403, detail="Game is over")
        
        result = advance_day(db)
        return {
            "success": True,
            "data": result,
            "message": None,
        }
    except SimulationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")
