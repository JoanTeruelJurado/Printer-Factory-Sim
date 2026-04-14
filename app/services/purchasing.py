"""
Purchasing service for managing purchase orders.

Handles purchase order creation, delivery, and supplier catalog queries.
"""

import random
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import (
    GameState,
    Inventory,
    Product,
    PurchaseOrder,
    RawMaterial,
    Supplier,
    SupplierProduct,
)


class PurchasingError(Exception):
    """Base exception for purchasing errors."""
    pass


def get_supplier_catalog(db: Session, supplier_id: int) -> dict:
    """
    Get supplier's product catalog with current pricing.
    
    Args:
        db: Database session
        supplier_id: ID of supplier
        
    Returns:
        Dict with supplier info and material catalog
    """
    supplier = db.query(Supplier).filter_by(id=supplier_id).first()
    if not supplier:
        raise PurchasingError(f"Supplier {supplier_id} not found")
    
    catalog = []
    for sp in supplier.supplier_products:
        current_price = sp.base_unit_cost * sp.daily_price_factor
        catalog.append({
            "material_id": sp.material_id,
            "material_name": sp.material.name,
            "base_unit_cost": sp.base_unit_cost,
            "daily_price_factor": sp.daily_price_factor,
            "current_price": current_price,
        })
    
    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "lead_time_days": supplier.lead_time_days,
        "reliability": supplier.reliability,
        "catalog": catalog,
    }


def get_material_pricing(db: Session, supplier_id: int, material_id: int) -> dict:
    """
    Get pricing for a specific material from a supplier.
    
    Args:
        db: Database session
        supplier_id: ID of supplier
        material_id: ID of material
        
    Returns:
        Dict with pricing details
    """
    sp = db.query(SupplierProduct).filter_by(
        supplier_id=supplier_id,
        material_id=material_id,
    ).first()
    
    if not sp:
        raise PurchasingError(
            f"Material {material_id} not available from supplier {supplier_id}"
        )
    
    material = sp.material
    supplier = sp.supplier
    current_price = sp.base_unit_cost * sp.daily_price_factor
    
    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "material_id": material.id,
        "material_name": material.name,
        "base_unit_cost": sp.base_unit_cost,
        "daily_price_factor": sp.daily_price_factor,
        "current_price_per_unit": current_price,
        "lead_time_days": supplier.lead_time_days,
    }


def issue_purchase_order(
    db: Session,
    supplier_id: int,
    material_id: int,
    quantity: int,
    current_day: int,
) -> PurchaseOrder:
    """
    Issue a new purchase order.
    
    Validates:
    - Supplier and material exist
    - Wallet has sufficient funds
    - Warehouse has sufficient capacity
    
    Args:
        db: Database session
        supplier_id: ID of supplier
        material_id: ID of material
        quantity: Quantity to order
        current_day: Current simulation day
        
    Returns:
        Created PurchaseOrder
        
    Raises:
        PurchasingError: If validation fails
    """
    # Validate supplier and material
    supplier = db.query(Supplier).filter_by(id=supplier_id).first()
    if not supplier:
        raise PurchasingError(f"Supplier {supplier_id} not found")
    
    material = db.query(RawMaterial).filter_by(id=material_id).first()
    if not material:
        raise PurchasingError(f"Material {material_id} not found")
    
    # Get supplier product pricing
    sp = db.query(SupplierProduct).filter_by(
        supplier_id=supplier_id,
        material_id=material_id,
    ).first()
    if not sp:
        raise PurchasingError(
            f"Material {material_id} not available from supplier {supplier_id}"
        )
    
    # Calculate cost
    unit_cost = sp.base_unit_cost * sp.daily_price_factor
    total_cost = unit_cost * quantity
    
    # Check wallet
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        raise PurchasingError("Game state not found")
    
    if game_state.wallet_balance < total_cost:
        raise PurchasingError(
            f"Insufficient funds: need €{total_cost:.2f}, have €{game_state.wallet_balance:.2f}"
        )
    
    # Check warehouse capacity
    inventory = db.query(Inventory).filter_by(material_id=material_id).first()
    current_used = sum(inv.quantity + inv.reserved_quantity 
                       for inv in db.query(Inventory).all())
    
    if current_used + quantity > game_state.warehouse_capacity:
        raise PurchasingError(
            f"Insufficient warehouse capacity: need {quantity} units, have {game_state.warehouse_capacity - current_used} free"
        )
    
    # Calculate expected delivery
    expected_delivery_day = current_day + supplier.lead_time_days
    
    # Create purchase order
    po = PurchaseOrder(
        supplier_id=supplier_id,
        material_id=material_id,
        quantity=quantity,
        packaging_type="unit",  # Simplified: always "unit" for now
        issue_day=current_day,
        expected_delivery_day=expected_delivery_day,
        status="pending",
        unit_cost=unit_cost,
        total_cost=total_cost,
    )
    db.add(po)
    db.flush()
    
    # Deduct from wallet immediately
    game_state.wallet_balance -= total_cost
    
    return po


def apply_price_fluctuation(db: Session) -> None:
    """
    Apply daily price fluctuation to all supplier products.
    
    Recalculates daily_price_factor (±10% random) for each supplier-material.
    
    Args:
        db: Database session
    """
    supplier_products = db.query(SupplierProduct).all()
    for sp in supplier_products:
        sp.daily_price_factor = random.uniform(0.90, 1.10)
    db.flush()


def list_suppliers(db: Session) -> list[dict]:
    """
    List all suppliers with basic info.
    
    Args:
        db: Database session
        
    Returns:
        List of supplier dicts
    """
    suppliers = db.query(Supplier).all()
    return [
        {
            "supplier_id": s.id,
            "supplier_name": s.name,
            "lead_time_days": s.lead_time_days,
            "reliability": s.reliability,
        }
        for s in suppliers
    ]


def list_purchase_orders(db: Session) -> list[dict]:
    """
    List all purchase orders.
    
    Args:
        db: Database session
        
    Returns:
        List of purchase order dicts
    """
    orders = db.query(PurchaseOrder).all()
    return [
        {
            "po_id": po.id,
            "supplier_id": po.supplier_id,
            "supplier_name": po.supplier.name,
            "material_id": po.material_id,
            "material_name": po.material.name,
            "quantity": po.quantity,
            "issue_day": po.issue_day,
            "expected_delivery_day": po.expected_delivery_day,
            "actual_delivery_day": po.actual_delivery_day,
            "status": po.status,
            "unit_cost": po.unit_cost,
            "total_cost": po.total_cost,
        }
        for po in orders
    ]
