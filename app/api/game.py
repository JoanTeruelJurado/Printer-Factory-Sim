import json
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.db.models import (
    Config, DemandOrder, Event, GameState, Inventory,
    ManufacturingOrder, Product,
)
from app.services import supplier_client
from app.schemas import GameStateResponse, InventoryItemResponse
from app.services.seed import reset_game
from app.services.simulation import advance_day, SimulationError


class ResetConfig(BaseModel):
    daily_production_capacity: int = Field(default=10, ge=1, le=500)
    starting_wallet: float = Field(default=10000.0, ge=0.0)

router = APIRouter()


@router.get("/state", response_model=GameStateResponse)
def get_game_state(db: Session = Depends(get_db)) -> GameStateResponse:
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")

    # reserved_quantity is already included in quantity — no double-counting
    warehouse_used = db.query(Inventory).with_entities(
        Inventory.quantity.label("used")
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

    released_qty = db.query(func.sum(ManufacturingOrder.remaining_qty)).filter(
        ManufacturingOrder.status == "released"
    ).scalar() or 0
    production_used_today = min(int(released_qty), state.daily_production_capacity)

    return GameStateResponse(
        current_day=state.current_day,
        wallet_balance=state.wallet_balance,
        warehouse_capacity=state.warehouse_capacity,
        warehouse_used=total_used,
        daily_production_capacity=state.daily_production_capacity,
        production_used_today=production_used_today,
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
def reset_game_state(
    config: Optional[ResetConfig] = Body(default=None),
    db: Session = Depends(get_db),
) -> dict:
    cfg = config or ResetConfig()
    reset_game(db, daily_production_capacity=cfg.daily_production_capacity, starting_wallet=cfg.starting_wallet)
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


@router.get("/export")
def export_game(db: Session = Depends(get_db)) -> JSONResponse:
    """Export full game state as a downloadable JSON snapshot."""
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")

    inventory = db.query(Inventory).all()
    manufacturing_orders = db.query(ManufacturingOrder).all()
    demand_orders = db.query(DemandOrder).all()
    try:
        purchase_orders = supplier_client.get_orders()
    except supplier_client.SupplierAPIError:
        purchase_orders = []
    events = db.query(Event).all()

    snapshot = {
        "exported_at": datetime.utcnow().isoformat(),
        "game_state": {
            "current_day": state.current_day,
            "wallet_balance": state.wallet_balance,
            "warehouse_capacity": state.warehouse_capacity,
            "daily_production_capacity": state.daily_production_capacity,
            "days_with_negative_balance": state.days_with_negative_balance,
            "game_over": state.game_over,
        },
        "inventory": [
            {"material_id": i.material_id, "quantity": i.quantity, "reserved_quantity": i.reserved_quantity}
            for i in inventory
        ],
        "manufacturing_orders": [
            {
                "id": mo.id, "product_id": mo.product_id, "quantity": mo.quantity,
                "remaining_qty": mo.remaining_qty, "status": mo.status,
                "created_day": mo.created_day, "release_day": mo.release_day,
                "completed_day": mo.completed_day,
            }
            for mo in manufacturing_orders
        ],
        "demand_orders": [
            {
                "id": do.id, "client_id": do.client_id, "product_id": do.product_id,
                "quantity": do.quantity, "fulfilled_qty": do.fulfilled_qty,
                "request_day": do.request_day, "due_day": do.due_day,
                "status": do.status, "penalty_amount": do.penalty_amount,
            }
            for do in demand_orders
        ],
        "purchase_orders": [
            {
                "id": po["id"], "supplier_id": po["supplier_id"], "material_id": po["material_id"],
                "material_name": po["material_name"], "quantity": po["quantity"],
                "packaging_type": po["packaging_type"],
                "issue_day": po["issue_day"], "expected_delivery_day": po["expected_delivery_day"],
                "actual_delivery_day": po.get("actual_delivery_day"),
                "status": po["status"], "unit_cost": po["unit_cost"], "total_cost": po["total_cost"],
            }
            for po in purchase_orders
        ],
        "events": [
            {
                "id": e.id, "event_type": e.event_type, "sim_day": e.sim_day,
                "category": e.category, "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }

    filename = f"factory_save_day{state.current_day}.json"
    return JSONResponse(
        content=snapshot,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def import_game(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """Import a game snapshot, replacing all transactional data."""
    required_keys = {"game_state", "inventory", "manufacturing_orders", "demand_orders", "purchase_orders"}
    if not required_keys.issubset(payload.keys()):
        raise HTTPException(status_code=422, detail=f"Missing keys: {required_keys - payload.keys()}")

    try:
        # Wipe transactional tables
        db.query(Event).delete()
        db.query(DemandOrder).delete()
        db.query(ManufacturingOrder).delete()
        try:
            supplier_client.reset_orders()
        except supplier_client.SupplierAPIError:
            pass  # Supplier API unavailable — skip PO reset

        # Restore game state
        gs_data = payload["game_state"]
        state = db.query(GameState).filter(GameState.id == 1).first()
        if state is None:
            raise HTTPException(status_code=404, detail="Game state not found")
        state.current_day = gs_data["current_day"]
        state.wallet_balance = gs_data["wallet_balance"]
        state.warehouse_capacity = gs_data["warehouse_capacity"]
        state.daily_production_capacity = gs_data["daily_production_capacity"]
        state.days_with_negative_balance = gs_data["days_with_negative_balance"]
        state.game_over = gs_data["game_over"]
        state.last_updated = datetime.utcnow()

        # Restore inventory
        for inv_data in payload["inventory"]:
            inv = db.query(Inventory).filter(Inventory.material_id == inv_data["material_id"]).first()
            if inv:
                inv.quantity = inv_data["quantity"]
                inv.reserved_quantity = inv_data["reserved_quantity"]

        db.flush()

        # Restore manufacturing orders (preserve IDs)
        for mo_data in payload["manufacturing_orders"]:
            db.add(ManufacturingOrder(
                id=mo_data["id"], product_id=mo_data["product_id"],
                quantity=mo_data["quantity"], remaining_qty=mo_data["remaining_qty"],
                status=mo_data["status"], created_day=mo_data["created_day"],
                release_day=mo_data.get("release_day"), completed_day=mo_data.get("completed_day"),
            ))

        # Restore demand orders
        for do_data in payload["demand_orders"]:
            db.add(DemandOrder(
                id=do_data["id"], client_id=do_data["client_id"],
                product_id=do_data["product_id"], quantity=do_data["quantity"],
                fulfilled_qty=do_data["fulfilled_qty"], request_day=do_data["request_day"],
                due_day=do_data["due_day"], status=do_data["status"],
                penalty_amount=do_data.get("penalty_amount", 0.0),
            ))

        # Restore purchase orders in Supplier API
        for po_data in payload["purchase_orders"]:
            try:
                supplier_client.create_order({
                    "supplier_id": po_data["supplier_id"],
                    "material_id": po_data["material_id"],
                    "material_name": po_data.get("material_name", str(po_data["material_id"])),
                    "quantity": po_data["quantity"],
                    "packaging_type": po_data.get("packaging_type", "unit"),
                    "issue_day": po_data["issue_day"],
                    "unit_cost": po_data["unit_cost"],
                    "total_cost": po_data["total_cost"],
                    "expected_delivery_day": po_data["expected_delivery_day"],
                })
            except supplier_client.SupplierAPIError:
                pass  # Supplier API unavailable — skip PO restore

        # Restore events (optional field)
        for ev_data in payload.get("events", []):
            db.add(Event(
                id=ev_data["id"], event_type=ev_data["event_type"],
                sim_day=ev_data["sim_day"], category=ev_data["category"],
                details=ev_data["details"],
                timestamp=datetime.fromisoformat(ev_data["timestamp"]),
            ))

        db.commit()
        return {"success": True, "message": f"Game imported at day {gs_data['current_day']}"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
