"""Order lifecycle management for the provider."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from provider_app.models import Event, Product, ProviderOrder, SimulationDay, Stock
from provider_app.services.catalog import compute_price


def _current_day(db: Session) -> int:
    sim = db.query(SimulationDay).filter_by(id=1).first()
    return sim.current_day if sim else 1


def create_order(db: Session, buyer: str, product_id: int, quantity: int) -> ProviderOrder:
    """Place a new purchase order.

    Computes price from tier breaks, sets expected delivery day, persists order
    in PENDING state, and writes an audit event.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    product = db.query(Product).filter_by(id=product_id, active=True).first()
    if not product:
        raise ValueError(f"Product {product_id} not found or inactive")

    unit_price = compute_price(db, product_id, quantity)
    total_price = unit_price * quantity
    current_day = _current_day(db)
    expected_delivery_day = current_day + product.lead_time_days

    order = ProviderOrder(
        buyer_name=buyer,
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        placed_day=current_day,
        expected_delivery_day=expected_delivery_day,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(order)
    db.flush()

    db.add(
        Event(
            event_type="order_placed",
            day=current_day,
            details=json.dumps(
                {
                    "order_id": order.id,
                    "buyer": buyer,
                    "product_id": product_id,
                    "product_name": product.name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "expected_delivery_day": expected_delivery_day,
                }
            ),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> ProviderOrder:
    """Fetch a single order or raise ValueError."""
    order = db.query(ProviderOrder).filter_by(id=order_id).first()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    return order


def list_orders(db: Session, status: str | None = None) -> list[ProviderOrder]:
    """List all orders, optionally filtered by status."""
    q = db.query(ProviderOrder)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(ProviderOrder.id.desc()).all()


def cancel_order(db: Session, order_id: int) -> ProviderOrder:
    """Cancel a pending or confirmed order.

    Restores stock if the order was already confirmed (stock was deducted).
    """
    order = db.query(ProviderOrder).filter_by(id=order_id).first()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    if order.status in ("shipped", "delivered"):
        raise ValueError(f"Cannot cancel order {order_id} with status '{order.status}'")
    if order.status == "cancelled":
        raise ValueError(f"Order {order_id} is already cancelled")

    # Restore stock if it was already deducted
    if order.status == "confirmed":
        stock = db.query(Stock).filter_by(product_id=order.product_id).first()
        if stock:
            stock.quantity += order.quantity

    current_day = _current_day(db)
    order.status = "cancelled"

    db.add(
        Event(
            event_type="order_cancelled",
            day=current_day,
            details=json.dumps({"order_id": order_id, "previous_status": order.status}),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(order)
    return order
