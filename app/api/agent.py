"""
Agent context endpoint.

GET /api/agent/context  — full game state in a single call, designed for
                          AI agents that need to make decisions without
                          issuing multiple round-trips.

The response includes:
  - game state (day, wallet, warehouse, production capacity)
  - raw-material inventory (available = quantity - reserved)
  - products with their full Bill of Materials
  - open demand orders (what the market wants)
  - active manufacturing orders
  - pending purchase orders
  - supplier catalog (stock + pricing tiers for every material)
  - per-material constraints (max purchasable given wallet / stock / warehouse)
  - action reference (which endpoints to call and with what payload)
"""

import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    BOM,
    DemandOrder,
    GameState,
    Inventory,
    ManufacturingOrder,
    Product,
    RawMaterial,
)
from app.services import supplier_client
from app.services.supplier_client import SupplierAPIError

router = APIRouter()


@router.get("/agent/context")
def agent_context(db: Session = Depends(get_db)) -> dict:
    """
    Return a complete snapshot of the simulation state for agent consumption.

    All information needed to decide what to buy, build, or fulfil is
    included in a single response.
    """
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        return {"error": "Game state not found"}

    wallet = game_state.wallet_balance
    warehouse_capacity = game_state.warehouse_capacity

    # ── Inventory ─────────────────────────────────────────────────────────────
    inventories = db.query(Inventory).all()
    inventory_map: dict[int, dict] = {}
    warehouse_used = 0.0
    for inv in inventories:
        available = inv.quantity - inv.reserved_quantity
        inventory_map[inv.material_id] = {
            "material_id": inv.material_id,
            "name": inv.material.name,
            "quantity": inv.quantity,
            "reserved": inv.reserved_quantity,
            "available": available,
            "volume_per_unit": inv.material.volume_per_unit,
        }
        warehouse_used += inv.quantity

    warehouse_free = warehouse_capacity - warehouse_used

    # ── Products + BOM ────────────────────────────────────────────────────────
    products = db.query(Product).filter_by(product_type="finished", status="active").all()

    # Finished-goods count: completed MO qty minus already-fulfilled demand qty
    fulfilled_by_product: dict[int, int] = {}
    for do in db.query(DemandOrder).filter(DemandOrder.status.in_(["fulfilled", "partial"])).all():
        fulfilled_by_product[do.product_id] = (
            fulfilled_by_product.get(do.product_id, 0) + do.fulfilled_qty
        )
    produced_by_product: dict[int, int] = {}
    for mo in db.query(ManufacturingOrder).filter_by(status="completed").all():
        produced_by_product[mo.product_id] = (
            produced_by_product.get(mo.product_id, 0) + mo.quantity
        )

    products_out = []
    for p in products:
        finished_available = max(
            0,
            produced_by_product.get(p.id, 0) - fulfilled_by_product.get(p.id, 0),
        )
        bom = [
            {
                "material_id": line.material_id,
                "material_name": line.material.name,
                "qty_needed": line.qty_needed,
                "available_in_inventory": inventory_map.get(line.material_id, {}).get("available", 0),
            }
            for line in p.bom_lines
        ]
        # Max producible given current available inventory
        max_producible = min(
            math.floor(
                inventory_map.get(line.material_id, {}).get("available", 0) / line.qty_needed
            )
            for line in p.bom_lines
        ) if p.bom_lines else 0

        products_out.append({
            "product_id": p.id,
            "name": p.name,
            "sell_price": p.sell_price,
            "assembly_time_hours": p.assembly_time_hours,
            "finished_goods_available": finished_available,
            "max_producible_now": max_producible,
            "bom": bom,
        })

    # ── Demand orders (open / partial) ────────────────────────────────────────
    demand_orders = (
        db.query(DemandOrder)
        .filter(DemandOrder.status.in_(["open", "partial"]))
        .order_by(DemandOrder.due_day)
        .all()
    )
    demand_out = []
    for do in demand_orders:
        remaining = do.quantity - do.fulfilled_qty
        demand_out.append({
            "demand_id": do.id,
            "product_id": do.product_id,
            "product_name": do.product.name,
            "quantity": do.quantity,
            "fulfilled_qty": do.fulfilled_qty,
            "remaining_qty": remaining,
            "request_day": do.request_day,
            "due_day": do.due_day,
            "days_remaining": do.due_day - game_state.current_day,
            "status": do.status,
            "potential_revenue": remaining * (do.product.sell_price or 0),
            "late_penalty_per_unit": 50.0,
        })

    # ── Manufacturing orders (active) ─────────────────────────────────────────
    mos = (
        db.query(ManufacturingOrder)
        .filter(ManufacturingOrder.status.in_(["pending", "released"]))
        .all()
    )
    mo_out = [
        {
            "mo_id": mo.id,
            "product_id": mo.product_id,
            "product_name": mo.product.name,
            "quantity": mo.quantity,
            "remaining_qty": mo.remaining_qty,
            "status": mo.status,
            "created_day": mo.created_day,
            "release_day": mo.release_day,
        }
        for mo in mos
    ]

    # ── Purchase orders (pending / shipped) ───────────────────────────────────
    try:
        all_pos = supplier_client.get_orders()
        po_out = [
            po for po in all_pos
            if po.get("status") in ("pending", "shipped", "delivered")
        ]
    except SupplierAPIError:
        po_out = []

    # ── Supplier catalog ──────────────────────────────────────────────────────
    suppliers_out = []
    try:
        raw_suppliers = supplier_client.get_suppliers()
        for s in raw_suppliers:
            catalog_data = supplier_client.get_catalog(s["id"])
            catalog_items = []
            for item in catalog_data.get("catalog", []):
                # Compute per-tier constraints
                tiers_with_constraints = []
                for tier in item.get("pricing_tiers", []):
                    effective_price = tier["unit_price"] * item["daily_price_factor"]
                    max_by_wallet = math.floor(wallet / effective_price) if effective_price > 0 else 0
                    max_by_stock = item.get("stock", 0)
                    max_by_wh = math.floor(warehouse_free)
                    tiers_with_constraints.append({
                        "min_quantity": tier["min_quantity"],
                        "unit_price": tier["unit_price"],
                        "effective_price": round(effective_price, 4),
                        "max_affordable": min(max_by_wallet, max_by_stock, max_by_wh),
                    })

                base_price = item["current_price"]
                max_by_wallet_base = math.floor(wallet / base_price) if base_price > 0 else 0
                catalog_items.append({
                    "material_id": item["material_id"],
                    "material_name": item["material_name"],
                    "current_price_per_unit": base_price,
                    "daily_price_factor": item["daily_price_factor"],
                    "stock": item.get("stock", 0),
                    "pricing_tiers": tiers_with_constraints,
                    "max_orderable": min(
                        item.get("stock", 0),
                        max_by_wallet_base,
                        math.floor(warehouse_free),
                    ),
                })
            suppliers_out.append({
                "supplier_id": s["id"],
                "name": s["name"],
                "lead_time_days": s["lead_time_days"],
                "reliability": s["reliability"],
                "catalog": catalog_items,
            })
    except SupplierAPIError:
        suppliers_out = []

    # ── Action reference ──────────────────────────────────────────────────────
    actions = {
        "advance_day": {
            "method": "POST",
            "url": "/api/game/advance-day",
            "description": "Advance simulation by one day. Triggers deliveries, production, demand expiry, cost deduction.",
        },
        "create_purchase_order": {
            "method": "POST",
            "url": "/api/purchase-orders",
            "body": {"supplier_id": "<int>", "material_id": "<int>", "quantity": "<int>"},
            "description": "Buy materials from a supplier. Wallet is debited immediately. Materials arrive after lead_time_days.",
        },
        "create_manufacturing_order": {
            "method": "POST",
            "url": "/api/manufacturing-orders",
            "body": {"product_id": "<int>", "quantity": "<int>"},
            "description": "Create a manufacturing order (status: pending). Must be released to start production.",
        },
        "release_manufacturing_order": {
            "method": "PUT",
            "url": "/api/manufacturing-orders/<mo_id>/release",
            "body": {"quantity": "<int — units to release (≤ MO quantity)>"},
            "description": "Release MO to production. Reserves required materials. Production completes next advance_day.",
        },
        "fulfill_demand": {
            "method": "POST",
            "url": "/api/game/demand-orders/<demand_id>/fulfill",
            "description": "Serve an open demand order from finished-goods inventory. Revenue is credited immediately.",
        },
        "get_full_context": {
            "method": "GET",
            "url": "/api/agent/context",
            "description": "This endpoint — refresh full state.",
        },
    }

    return {
        "game": {
            "current_day": game_state.current_day,
            "wallet": wallet,
            "warehouse": {
                "capacity": warehouse_capacity,
                "used": warehouse_used,
                "free": warehouse_free,
            },
            "daily_production_capacity": game_state.daily_production_capacity,
            "game_over": game_state.game_over,
            "days_with_negative_balance": game_state.days_with_negative_balance,
        },
        "inventory": list(inventory_map.values()),
        "products": products_out,
        "demand_orders": demand_out,
        "manufacturing_orders": mo_out,
        "purchase_orders": po_out,
        "suppliers": suppliers_out,
        "actions": actions,
    }
