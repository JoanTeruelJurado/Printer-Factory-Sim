"""
Purchasing service for managing purchase orders.

All supplier/catalog/pricing data is fetched from the Supplier API via
supplier_client.  Wallet validation and warehouse capacity checks remain
here as factory-side business logic.
"""

from sqlalchemy.orm import Session

from app.db.models import GameState, Inventory, LocalPurchaseOrder
from app.services import supplier_client
from app.services.supplier_client import SupplierAPIError


class PurchasingError(Exception):
    """Base exception for purchasing errors."""
    pass


def list_suppliers(db: Session) -> list[dict]:
    """
    List all suppliers.

    Args:
        db: Database session (unused — kept for signature compatibility)

    Returns:
        List of supplier dicts from the Supplier API.
    """
    try:
        raw = supplier_client.get_suppliers()
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not reach Supplier API: {exc}") from exc

    # Normalise field names to match original response format
    return [
        {
            "supplier_id": s["id"],
            "supplier_name": s["name"],
            "lead_time_days": s["lead_time_days"],
            "reliability": s["reliability"],
        }
        for s in raw
    ]


def get_supplier_catalog(db: Session, supplier_id: int) -> dict:
    """
    Get supplier's product catalog with current pricing.

    Args:
        db: Database session (unused — kept for signature compatibility)
        supplier_id: ID of supplier

    Returns:
        Dict with supplier info and material catalog.
    """
    try:
        data = supplier_client.get_catalog(supplier_id)
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not reach Supplier API: {exc}") from exc

    return {
        "supplier_id": data["supplier_id"],
        "supplier_name": data["supplier_name"],
        "lead_time_days": data["lead_time_days"],
        "reliability": data["reliability"],
        "catalog": data["catalog"],
    }


def get_material_pricing(
    db: Session, supplier_id: int, material_id: int, quantity: int | None = None
) -> dict:
    """
    Get pricing for a specific material from a supplier.

    If *quantity* is provided, the returned price reflects the applicable
    volume-discount tier (as computed by the Supplier API).
    """
    try:
        data = supplier_client.get_pricing(supplier_id, material_id, quantity=quantity)
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not reach Supplier API: {exc}") from exc

    return data


def list_purchase_orders(db: Session) -> list[dict]:
    """
    List all purchase orders.

    Args:
        db: Database session (unused — kept for signature compatibility)

    Returns:
        List of purchase order dicts from the Supplier API.
    """
    try:
        raw = supplier_client.get_orders()
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not reach Supplier API: {exc}") from exc

    return [
        {
            "po_id": po["id"],
            "supplier_id": po["supplier_id"],
            # Supplier API doesn't store supplier_name on the order row,
            # so we fall back to supplier_id as a string if absent.
            "supplier_name": po.get("supplier_name", str(po["supplier_id"])),
            "material_id": po["material_id"],
            "material_name": po["material_name"],
            "quantity": po["quantity"],
            "issue_day": po["issue_day"],
            "expected_delivery_day": po["expected_delivery_day"],
            "actual_delivery_day": po.get("actual_delivery_day"),
            "status": po["status"],
            "unit_cost": po["unit_cost"],
            "total_cost": po["total_cost"],
        }
        for po in raw
    ]


def issue_purchase_order(
    db: Session,
    supplier_id: int,
    material_id: int,
    quantity: int,
    current_day: int,
) -> dict:
    """
    Issue a new purchase order.

    Flow:
    1. Fetch pricing from Supplier API.
    2. Calculate total cost.
    3. Check factory wallet (local GameState).
    4. Check warehouse capacity (local Inventory).
    5. Call Supplier API to create the order.
    6. Deduct wallet locally.
    7. Return the order data dict.

    Args:
        db: Database session
        supplier_id: ID of supplier
        material_id: ID of material
        quantity: Quantity to order
        current_day: Current simulation day

    Returns:
        Dict with purchase order details.

    Raises:
        PurchasingError: If validation fails or Supplier API is unreachable.
    """
    # 1. Get pricing — pass quantity so the Supplier applies volume-tier discounts
    try:
        pricing = supplier_client.get_pricing(supplier_id, material_id, quantity=quantity)
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not reach Supplier API: {exc}") from exc

    material_name = pricing["material_name"]
    unit_cost = pricing["current_price_per_unit"]  # tier-adjusted × daily factor
    lead_time_days = pricing["lead_time_days"]

    # 2. Calculate cost
    total_cost = unit_cost * quantity
    expected_delivery_day = current_day + lead_time_days

    # 3. Check wallet
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        raise PurchasingError("Game state not found")

    if game_state.wallet_balance < total_cost:
        raise PurchasingError(
            f"Insufficient funds: need \u20ac{total_cost:.2f}, "
            f"have \u20ac{game_state.wallet_balance:.2f}"
        )

    # 4. Check warehouse capacity
    current_used = sum(
        inv.quantity + inv.reserved_quantity
        for inv in db.query(Inventory).all()
    )
    if current_used + quantity > game_state.warehouse_capacity:
        free = game_state.warehouse_capacity - current_used
        raise PurchasingError(
            f"Insufficient warehouse capacity: need {quantity} units, have {free:.0f} free"
        )

    # 5. Create order in Supplier API
    payload = {
        "supplier_id": supplier_id,
        "material_id": material_id,
        "material_name": material_name,
        "quantity": quantity,
        "packaging_type": "unit",
        "issue_day": current_day,
        "unit_cost": unit_cost,
        "total_cost": total_cost,
        "expected_delivery_day": expected_delivery_day,
    }
    try:
        order_data = supplier_client.create_order(payload)
    except SupplierAPIError as exc:
        raise PurchasingError(f"Could not create order in Supplier API: {exc}") from exc

    # 6. Deduct wallet
    game_state.wallet_balance -= total_cost

    # 7. Save a local copy so the factory knows what is on the way
    local_po = LocalPurchaseOrder(
        supplier_po_id=order_data["id"],
        supplier_id=order_data["supplier_id"],
        supplier_name=pricing.get("supplier_name", str(supplier_id)),
        material_id=order_data["material_id"],
        material_name=order_data["material_name"],
        quantity=order_data["quantity"],
        unit_cost=order_data["unit_cost"],
        total_cost=order_data["total_cost"],
        issue_day=order_data["issue_day"],
        expected_delivery_day=order_data["expected_delivery_day"],
        status="pending",
    )
    db.add(local_po)

    # 8. Return normalised order dict (matches original PurchaseOrder field names)
    return {
        "po_id": order_data["id"],
        "supplier_id": order_data["supplier_id"],
        "supplier_name": pricing.get("supplier_name", str(supplier_id)),
        "material_id": order_data["material_id"],
        "material_name": order_data["material_name"],
        "quantity": order_data["quantity"],
        "packaging_type": order_data["packaging_type"],
        "issue_day": order_data["issue_day"],
        "expected_delivery_day": order_data["expected_delivery_day"],
        "actual_delivery_day": order_data.get("actual_delivery_day"),
        "status": order_data["status"],
        "unit_cost": order_data["unit_cost"],
        "total_cost": order_data["total_cost"],
    }
