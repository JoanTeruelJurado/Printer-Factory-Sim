"""Day-advancement engine for the provider simulation.

Day advance steps (executed in order, all in one transaction):
  1. SHIPPED orders with expected_delivery_day <= current_day  →  DELIVERED
  2. CONFIRMED orders                                          →  SHIPPED
  3. PENDING orders with sufficient stock                      →  CONFIRMED (stock deducted)
  4. current_day increments
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from provider_app.models import Event, ProviderOrder, SimulationDay, Stock


def get_current_day(db: Session) -> int:
    """Return the provider's current simulation day."""
    sim = db.query(SimulationDay).filter_by(id=1).first()
    return sim.current_day if sim else 1


def advance_day(db: Session) -> dict:
    """Process one simulation day and increment the day counter.

    Returns a summary dict with the previous/new day numbers and a list of
    every order state transition that occurred.
    """
    sim = db.query(SimulationDay).filter_by(id=1).first()
    if not sim:
        raise RuntimeError("Simulation state not initialised — run seed first")

    current_day = sim.current_day
    transitions: list[dict] = []

    # Step 1: SHIPPED → DELIVERED
    shipped = (
        db.query(ProviderOrder)
        .filter(
            ProviderOrder.status == "shipped",
            ProviderOrder.expected_delivery_day <= current_day,
        )
        .all()
    )
    for order in shipped:
        order.status = "delivered"
        order.delivered_day = current_day
        db.add(
            Event(
                event_type="order_delivered",
                day=current_day,
                details=json.dumps(
                    {
                        "order_id": order.id,
                        "buyer": order.buyer_name,
                        "product_id": order.product_id,
                        "product_name": order.product.name,
                        "quantity": order.quantity,
                    }
                ),
                created_at=datetime.utcnow(),
            )
        )
        transitions.append({"order_id": order.id, "transition": "shipped→delivered"})

    # Step 2: CONFIRMED → SHIPPED
    confirmed = db.query(ProviderOrder).filter_by(status="confirmed").all()
    for order in confirmed:
        order.status = "shipped"
        order.shipped_day = current_day
        db.add(
            Event(
                event_type="order_shipped",
                day=current_day,
                details=json.dumps(
                    {
                        "order_id": order.id,
                        "buyer": order.buyer_name,
                        "product_id": order.product_id,
                        "quantity": order.quantity,
                        "expected_delivery_day": order.expected_delivery_day,
                    }
                ),
                created_at=datetime.utcnow(),
            )
        )
        transitions.append({"order_id": order.id, "transition": "confirmed→shipped"})

    # Step 3: PENDING → CONFIRMED (if stock available)
    pending = db.query(ProviderOrder).filter_by(status="pending").all()
    for order in pending:
        stock = db.query(Stock).filter_by(product_id=order.product_id).first()
        if stock and stock.quantity >= order.quantity:
            stock.quantity -= order.quantity
            order.status = "confirmed"
            order.confirmed_day = current_day
            db.add(
                Event(
                    event_type="order_confirmed",
                    day=current_day,
                    details=json.dumps(
                        {
                            "order_id": order.id,
                            "buyer": order.buyer_name,
                            "product_id": order.product_id,
                            "quantity": order.quantity,
                            "stock_remaining": stock.quantity,
                        }
                    ),
                    created_at=datetime.utcnow(),
                )
            )
            transitions.append({"order_id": order.id, "transition": "pending→confirmed"})
        else:
            # Log insufficient stock (order stays pending)
            available = stock.quantity if stock else 0
            db.add(
                Event(
                    event_type="order_stock_insufficient",
                    day=current_day,
                    details=json.dumps(
                        {
                            "order_id": order.id,
                            "product_id": order.product_id,
                            "needed": order.quantity,
                            "available": available,
                        }
                    ),
                    created_at=datetime.utcnow(),
                )
            )

    # Step 4: Advance day
    sim.current_day += 1

    db.add(
        Event(
            event_type="day_advanced",
            day=current_day,
            details=json.dumps(
                {
                    "from_day": current_day,
                    "to_day": sim.current_day,
                    "order_transitions": len(transitions),
                }
            ),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()

    return {
        "previous_day": current_day,
        "current_day": sim.current_day,
        "transitions": transitions,
    }
