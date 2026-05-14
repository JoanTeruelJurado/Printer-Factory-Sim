"""
Production service for manufacturing order management.

Handles creation, release, and cancellation of manufacturing orders.
"""

from sqlalchemy.orm import Session

from app.db.models import ManufacturingOrder, GameState, Product
from app.services.inventory import reserve_materials, check_material_availability, unreserve_materials


class ProductionError(Exception):
    """Base exception for production errors."""
    pass


def create_manufacturing_order(
    db: Session,
    product_id: int,
    quantity: int,
    current_day: int,
) -> ManufacturingOrder:
    """
    Create a new manufacturing order.
    
    Args:
        db: Database session
        product_id: ID of product to manufacture
        quantity: Quantity to produce
        current_day: Current simulation day
        
    Returns:
        Created ManufacturingOrder
        
    Raises:
        ProductionError: If product not found or invalid quantity
    """
    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        raise ProductionError(f"Product {product_id} not found")
    
    if quantity <= 0:
        raise ProductionError("Quantity must be positive")
    
    order = ManufacturingOrder(
        product_id=product_id,
        quantity=quantity,
        created_day=current_day,
        status="pending",
        remaining_qty=quantity,
    )
    db.add(order)
    db.flush()
    
    return order


def release_manufacturing_order(
    db: Session,
    order_id: int,
    quantity_to_release: int,
) -> ManufacturingOrder:
    """
    Release a manufacturing order to production.
    
    Validates material availability and reserves materials.
    Supports partial release.
    
    Args:
        db: Database session
        order_id: ID of manufacturing order
        quantity_to_release: Quantity to release (can be partial)
        
    Returns:
        Updated ManufacturingOrder
        
    Raises:
        ProductionError: If order not found, invalid quantity, or insufficient materials
    """
    order = db.query(ManufacturingOrder).filter_by(id=order_id).first()
    if not order:
        raise ProductionError(f"Manufacturing order {order_id} not found")
    
    if order.status != "pending":
        raise ProductionError(f"Order {order_id} is already {order.status}")
    
    if quantity_to_release <= 0 or quantity_to_release > order.remaining_qty:
        raise ProductionError(
            f"Invalid release quantity: {quantity_to_release}, remaining: {order.remaining_qty}"
        )
    
    # Check material availability
    availability = check_material_availability(db, order.product_id, quantity_to_release)
    if not availability["fully_available"]:
        shortage_msg = "; ".join([
            f"{s['material_name']}: need {s['required']}, have {s['available']}"
            for s in availability["shortages"]
        ])
        raise ProductionError(f"Insufficient materials: {shortage_msg}")
    
    current_day = db.query(GameState).filter_by(id=1).first().current_day

    if quantity_to_release == order.remaining_qty:
        # Full release
        order.status = "released"
        order.release_day = current_day
        reserve_materials(db, order_id)
    else:
        # Partial release: split into a new released order + keep original pending
        remainder = order.remaining_qty - quantity_to_release
        order.quantity = order.quantity - quantity_to_release
        order.remaining_qty = remainder
        # order stays "pending" with the remainder

        released_order = ManufacturingOrder(
            product_id=order.product_id,
            quantity=quantity_to_release,
            created_day=order.created_day,
            release_day=current_day,
            status="released",
            remaining_qty=quantity_to_release,
        )
        db.add(released_order)
        db.flush()
        reserve_materials(db, released_order.id)
        db.flush()
        return released_order

    db.flush()
    return order


def cancel_manufacturing_order(db: Session, order_id: int) -> ManufacturingOrder:
    """
    Cancel a manufacturing order.
    
    Can only cancel pending orders. Releases any reserved materials.
    
    Args:
        db: Database session
        order_id: ID of manufacturing order
        
    Returns:
        Cancelled ManufacturingOrder
        
    Raises:
        ProductionError: If order not found or cannot be cancelled
    """
    order = db.query(ManufacturingOrder).filter_by(id=order_id).first()
    if not order:
        raise ProductionError(f"Manufacturing order {order_id} not found")
    
    if order.status == "pending":
        order.status = "cancelled"
    elif order.status == "released":
        unreserve_materials(db, order_id)
        order.status = "cancelled"
    else:
        raise ProductionError(f"Cannot cancel order in {order.status} status")
    
    db.flush()
    return order


def get_order_requirements(db: Session, order_id: int) -> dict:
    """
    Get material requirements for a manufacturing order.
    
    Args:
        db: Database session
        order_id: ID of manufacturing order
        
    Returns:
        Dict with BOM details and current availability
    """
    order = db.query(ManufacturingOrder).filter_by(id=order_id).first()
    if not order:
        raise ProductionError(f"Manufacturing order {order_id} not found")
    
    from app.db.models import Inventory
    
    bom_details = []
    for bom in order.product.bom_lines:
        required = bom.qty_needed * order.remaining_qty
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        available = (inventory.quantity - inventory.reserved_quantity) if inventory else 0
        
        bom_details.append({
            "material_id": bom.material_id,
            "material_name": bom.material.name,
            "qty_per_unit": bom.qty_needed,
            "total_required": required,
            "available": available,
            "shortage": max(0, required - available),
        })
    
    return {
        "order_id": order_id,
        "product_id": order.product_id,
        "product_name": order.product.name,
        "quantity": order.quantity,
        "remaining_qty": order.remaining_qty,
        "status": order.status,
        "bom": bom_details,
    }
