"""
Inventory management service for the factory simulator.

Handles material reservation, consumption, and availability checking.
"""

from sqlalchemy.orm import Session

from app.db.models import Inventory, ManufacturingOrder


def reserve_materials(db: Session, manufacturing_order_id: int) -> None:
    """
    Reserve materials for a manufacturing order.
    
    Marks materials as reserved when order is released.
    
    Args:
        db: Database session
        manufacturing_order_id: ID of manufacturing order
        
    Raises:
        ValueError: If order not found or materials unavailable
    """
    order = db.query(ManufacturingOrder).filter_by(id=manufacturing_order_id).first()
    if not order:
        raise ValueError(f"Manufacturing order {manufacturing_order_id} not found")
    
    # Calculate materials needed based on remaining quantity
    qty_to_reserve = order.remaining_qty
    
    for bom in order.product.bom_lines:
        required = bom.qty_needed * qty_to_reserve
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        
        if not inventory:
            raise ValueError(f"Inventory record not found for material {bom.material_id}")
        
        # Check if enough available (not reserved)
        available = inventory.quantity - inventory.reserved_quantity
        if available < required:
            raise ValueError(
                f"Insufficient {bom.material.name}: need {required}, available {available}"
            )
        
        # Mark as reserved
        inventory.reserved_quantity += required


def consume_materials(db: Session, manufacturing_order_id: int, units_produced: int) -> None:
    """
    Consume materials from inventory when production completes.
    
    Args:
        db: Database session
        manufacturing_order_id: ID of manufacturing order
        units_produced: Number of units produced
    """
    order = db.query(ManufacturingOrder).filter_by(id=manufacturing_order_id).first()
    if not order:
        raise ValueError(f"Manufacturing order {manufacturing_order_id} not found")
    
    for bom in order.product.bom_lines:
        required = bom.qty_needed * units_produced
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        
        if inventory:
            inventory.quantity -= required
            inventory.reserved_quantity -= required


def check_material_availability(
    db: Session,
    product_id: int,
    quantity: int,
) -> dict:
    """
    Check if materials are available to fulfill an order.
    
    Args:
        db: Database session
        product_id: ID of product to manufacture
        quantity: Quantity to produce
        
    Returns:
        Dict with availability info and shortages (if any)
    """
    from app.db.models import Product
    
    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        raise ValueError(f"Product {product_id} not found")
    
    shortages = []
    fully_available = True
    
    for bom in product.bom_lines:
        required = bom.qty_needed * quantity
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        available = (inventory.quantity - inventory.reserved_quantity) if inventory else 0
        
        if available < required:
            fully_available = False
            shortages.append({
                "material_id": bom.material_id,
                "material_name": bom.material.name,
                "required": required,
                "available": available,
                "shortage": required - available,
            })
    
    return {
        "fully_available": fully_available,
        "shortages": shortages,
    }


def unreserve_materials(db: Session, manufacturing_order_id: int) -> None:
    """
    Release reserved materials back to available stock for a cancelled order.

    Args:
        db: Database session
        manufacturing_order_id: ID of manufacturing order being cancelled
    """
    order = db.query(ManufacturingOrder).filter_by(id=manufacturing_order_id).first()
    if not order:
        raise ValueError(f"Manufacturing order {manufacturing_order_id} not found")

    qty_reserved = order.remaining_qty
    for bom in order.product.bom_lines:
        required = bom.qty_needed * qty_reserved
        inventory = db.query(Inventory).filter_by(material_id=bom.material_id).first()
        if inventory:
            inventory.reserved_quantity = max(0.0, inventory.reserved_quantity - required)


def get_available_quantity(db: Session, material_id: int) -> float:
    """
    Get available (unreserved) quantity for a material.
    
    Args:
        db: Database session
        material_id: ID of material
        
    Returns:
        Available quantity
    """
    inventory = db.query(Inventory).filter_by(material_id=material_id).first()
    if not inventory:
        return 0.0
    
    return inventory.quantity - inventory.reserved_quantity
