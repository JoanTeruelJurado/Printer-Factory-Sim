"""
Agent context endpoint for the Retailer.

GET /api/agent/context  — full retailer state in a single call, designed for
                          AI agents that need to make decisions without
                          issuing multiple round-trips.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from retailer.database import get_db
from retailer.models import (
    Catalog,
    CustomerOrder,
    RetailerGameState,
    RetailerPurchaseOrder,
    RetailerStock,
)

router = APIRouter()


@router.get("/agent/context")
def agent_context(db: Session = Depends(get_db)) -> dict:
    """Return a complete snapshot of the retailer state for agent consumption."""
    game_state = db.query(RetailerGameState).filter_by(id=1).first()
    if not game_state:
        return {"error": "Retailer game state not found"}

    # ── Catalog + Stock ──────────────────────────────────────────────────────
    catalog_items = db.query(Catalog).all()
    stock_map: dict[str, int] = {}
    for s in db.query(RetailerStock).all():
        stock_map[s.model_name] = s.quantity_on_hand

    catalog_out = []
    for item in catalog_items:
        catalog_out.append({
            "model_name": item.model_name,
            "description": item.description,
            "retail_price": item.retail_price,
            "wholesale_price": item.wholesale_price,
            "stock_on_hand": stock_map.get(item.model_name, 0),
        })

    # ── Customer orders (pending / backordered) ──────────────────────────────
    open_orders = (
        db.query(CustomerOrder)
        .filter(CustomerOrder.status.in_(["pending", "backordered"]))
        .order_by(CustomerOrder.order_day)
        .all()
    )
    orders_out = [
        {
            "order_id": o.id,
            "customer": o.customer_name,
            "model": o.model_name,
            "quantity": o.quantity,
            "status": o.status,
            "order_day": o.order_day,
        }
        for o in open_orders
    ]

    # ── Purchase orders (pending / shipped) ──────────────────────────────────
    active_pos = (
        db.query(RetailerPurchaseOrder)
        .filter(RetailerPurchaseOrder.status.in_(["pending", "shipped"]))
        .order_by(RetailerPurchaseOrder.expected_delivery_day)
        .all()
    )
    pos_out = [
        {
            "po_id": po.id,
            "model": po.model_name,
            "quantity": po.quantity,
            "status": po.status,
            "ordered_day": po.ordered_day,
            "expected_delivery_day": po.expected_delivery_day,
            "unit_price": po.unit_price,
            "total_price": po.total_price,
        }
        for po in active_pos
    ]

    # ── Recent fulfillment stats (last 5 days) ──────────────────────────────
    lookback = max(1, game_state.current_day - 4)
    recent_fulfilled = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.status == "fulfilled",
            CustomerOrder.fulfilled_day >= lookback,
        )
        .count()
    )
    recent_backordered = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.status == "backordered",
            CustomerOrder.order_day >= lookback,
        )
        .count()
    )

    return {
        "game": {
            "current_day": game_state.current_day,
            "wallet": game_state.wallet_balance,
        },
        "catalog": catalog_out,
        "open_orders": orders_out,
        "purchase_orders": pos_out,
        "stats": {
            "recent_fulfilled_5d": recent_fulfilled,
            "recent_backordered_5d": recent_backordered,
            "pending_orders": len([o for o in orders_out if o["status"] == "pending"]),
            "backordered_orders": len([o for o in orders_out if o["status"] == "backordered"]),
        },
        "actions": {
            "fulfill_order": {
                "method": "PUT",
                "url": "/api/orders/<order_id>/fulfill",
            },
            "backorder_order": {
                "method": "PUT",
                "url": "/api/orders/<order_id>/backorder",
            },
            "create_purchase": {
                "method": "POST",
                "url": "/api/purchases",
                "body": {"model": "<str>", "quantity": "<int>"},
            },
            "set_price": {
                "method": "PUT",
                "url": "/api/catalog/<model_name>/price",
                "body": {"retail_price": "<float>"},
            },
        },
    }
