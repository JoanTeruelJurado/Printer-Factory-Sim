"""
Sales service for inbound order management.

Handles creation and querying of sales orders received from retailers.
"""

from sqlalchemy.orm import Session

from app.db.models import GameState, Inventory, Product, SalesOrder
from app.services.inventory import check_material_availability


class SalesError(Exception):
    """Base exception for sales errors."""
    pass


def create_sales_order(
    db: Session,
    retailer_name: str,
    product_name: str,
    quantity: int,
    current_day: int,
) -> SalesOrder:
    """
    Create a new sales order from a retailer.

    Args:
        db: Database session
        retailer_name: Name of the retailer placing the order
        product_name: Name of the product (must be a finished product)
        quantity: Quantity ordered
        current_day: Current simulation day

    Returns:
        Created SalesOrder

    Raises:
        SalesError: If product not found, not finished, or invalid quantity
    """
    if quantity <= 0:
        raise SalesError("Quantity must be positive")

    product = (
        db.query(Product)
        .filter(Product.name == product_name, Product.product_type == "finished")
        .first()
    )
    if not product:
        raise SalesError(f"Finished product '{product_name}' not found")

    if product.sell_price is None:
        raise SalesError(f"Product '{product_name}' has no sell price configured")

    unit_price = product.sell_price
    total_price = unit_price * quantity

    order = SalesOrder(
        retailer_name=retailer_name,
        product_id=product.id,
        quantity=quantity,
        status="pending",
        ordered_day=current_day,
        unit_price=unit_price,
        total_price=total_price,
    )
    db.add(order)
    db.flush()

    return order


def list_sales_orders(
    db: Session,
    status: str | None = None,
) -> list[SalesOrder]:
    """
    List sales orders, optionally filtered by status.

    Args:
        db: Database session
        status: Optional status filter

    Returns:
        List of SalesOrder objects
    """
    query = db.query(SalesOrder)
    if status:
        query = query.filter(SalesOrder.status == status)
    return query.order_by(SalesOrder.id.desc()).all()


def get_sales_order(db: Session, order_id: int) -> SalesOrder | None:
    """
    Get a single sales order by ID.

    Args:
        db: Database session
        order_id: Sales order ID

    Returns:
        SalesOrder or None
    """
    return db.query(SalesOrder).filter(SalesOrder.id == order_id).first()


def release_sales_order(
    db: Session,
    order_id: int,
    quantity: int | None = None,
) -> SalesOrder:
    """
    Release a sales order to production.

    Validates material availability, reserves materials, and sets status
    to 'released'. Sales orders do not support partial release.

    Args:
        db: Database session
        order_id: Sales order ID
        quantity: Ignored for sales orders (always releases full quantity)

    Returns:
        Updated SalesOrder

    Raises:
        SalesError: If order not found, not pending, or insufficient materials
    """
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise SalesError(f"Sales order {order_id} not found")

    if order.status != "pending":
        raise SalesError(f"Sales order {order_id} is already {order.status}")

    # Check material availability
    availability = check_material_availability(db, order.product_id, order.quantity)
    if not availability["fully_available"]:
        shortage_msg = "; ".join([
            f"{s['material_name']}: need {s['required']}, have {s['available']}"
            for s in availability["shortages"]
        ])
        raise SalesError(f"Insufficient materials: {shortage_msg}")

    # Reserve materials (same logic as inventory.reserve_materials but for SalesOrder)
    for bom in order.product.bom_lines:
        required = bom.qty_needed * order.quantity
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        if not inventory:
            raise SalesError(f"Inventory record not found for material {bom.material_id}")
        inventory.reserved_quantity += required

    # Update order status
    game_state = db.query(GameState).filter_by(id=1).first()
    order.status = "released"
    order.released_day = game_state.current_day if game_state else 0

    db.flush()
    return order
