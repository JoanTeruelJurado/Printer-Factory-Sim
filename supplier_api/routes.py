"""
Supplier API route handlers.

Endpoints:
  GET  /suppliers                          — list all suppliers
  GET  /suppliers/{id}/catalog             — catalog with current prices
  GET  /suppliers/{id}/pricing/{mat_id}    — single material pricing
  POST /orders                             — create purchase order
  GET  /orders                             — list all purchase orders
  GET  /orders/due                         — orders due by ?day=N
  PUT  /orders/{id}/deliver                — mark order as delivered
  POST /prices/fluctuate                   — apply ±10% price fluctuation
  GET  /health                             — health check
"""

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supplier_api.database import get_db
from supplier_api.models import PurchaseOrder, Supplier, SupplierProduct

router = APIRouter()


# ── Pydantic schemas (local, lightweight) ─────────────────────────────────────

class SupplierOut(BaseModel):
    id: int
    name: str
    lead_time_days: int
    reliability: float

    class Config:
        from_attributes = True


class CatalogItemOut(BaseModel):
    material_id: int
    material_name: str
    base_unit_cost: float
    daily_price_factor: float
    current_price: float

    class Config:
        from_attributes = True


class SupplierCatalogOut(BaseModel):
    supplier_id: int
    supplier_name: str
    lead_time_days: int
    reliability: float
    catalog: list[CatalogItemOut]

    class Config:
        from_attributes = True


class MaterialPricingOut(BaseModel):
    supplier_id: int
    supplier_name: str
    material_id: int
    material_name: str
    base_unit_cost: float
    daily_price_factor: float
    current_price_per_unit: float
    lead_time_days: int

    class Config:
        from_attributes = True


class CreateOrderRequest(BaseModel):
    supplier_id: int
    material_id: int
    material_name: str
    quantity: int
    packaging_type: str = "unit"
    issue_day: int
    unit_cost: float
    total_cost: float
    expected_delivery_day: int


class DeliverOrderRequest(BaseModel):
    actual_delivery_day: int


class PurchaseOrderOut(BaseModel):
    id: int
    supplier_id: int
    material_id: int
    material_name: str
    quantity: int
    packaging_type: str
    issue_day: int
    expected_delivery_day: int
    actual_delivery_day: int | None
    status: str
    unit_cost: float
    total_cost: float

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_supplier_or_404(db: Session, supplier_id: int) -> Supplier:
    s = db.query(Supplier).filter_by(id=supplier_id).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return s


def _get_order_or_404(db: Session, order_id: int) -> PurchaseOrder:
    po = db.query(PurchaseOrder).filter_by(id=order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail=f"Purchase order {order_id} not found")
    return po


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "supplier-api"}


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)) -> list[SupplierOut]:
    """List all suppliers."""
    return db.query(Supplier).all()


@router.get("/suppliers/{supplier_id}/catalog", response_model=SupplierCatalogOut)
def get_catalog(supplier_id: int, db: Session = Depends(get_db)) -> SupplierCatalogOut:
    """Get supplier's product catalog with current prices (base * daily_factor)."""
    supplier = _get_supplier_or_404(db, supplier_id)
    catalog = []
    for sp in supplier.supplier_products:
        catalog.append(CatalogItemOut(
            material_id=sp.material_id,
            material_name=sp.material_name,
            base_unit_cost=sp.base_unit_cost,
            daily_price_factor=sp.daily_price_factor,
            current_price=sp.base_unit_cost * sp.daily_price_factor,
        ))
    return SupplierCatalogOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        lead_time_days=supplier.lead_time_days,
        reliability=supplier.reliability,
        catalog=catalog,
    )


@router.get("/suppliers/{supplier_id}/pricing/{material_id}", response_model=MaterialPricingOut)
def get_pricing(
    supplier_id: int,
    material_id: int,
    db: Session = Depends(get_db),
) -> MaterialPricingOut:
    """Get pricing for a specific material from a supplier."""
    supplier = _get_supplier_or_404(db, supplier_id)
    sp = (
        db.query(SupplierProduct)
        .filter_by(supplier_id=supplier_id, material_id=material_id)
        .first()
    )
    if not sp:
        raise HTTPException(
            status_code=404,
            detail=f"Material {material_id} not available from supplier {supplier_id}",
        )
    return MaterialPricingOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        material_id=sp.material_id,
        material_name=sp.material_name,
        base_unit_cost=sp.base_unit_cost,
        daily_price_factor=sp.daily_price_factor,
        current_price_per_unit=sp.base_unit_cost * sp.daily_price_factor,
        lead_time_days=supplier.lead_time_days,
    )


@router.post("/orders", response_model=PurchaseOrderOut, status_code=201)
def create_order(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    """Create a new purchase order."""
    # Validate supplier exists
    _get_supplier_or_404(db, req.supplier_id)

    po = PurchaseOrder(
        supplier_id=req.supplier_id,
        material_id=req.material_id,
        material_name=req.material_name,
        quantity=req.quantity,
        packaging_type=req.packaging_type,
        issue_day=req.issue_day,
        expected_delivery_day=req.expected_delivery_day,
        status="pending",
        unit_cost=req.unit_cost,
        total_cost=req.total_cost,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


@router.get("/orders", response_model=list[PurchaseOrderOut])
def list_orders(db: Session = Depends(get_db)) -> list[PurchaseOrderOut]:
    """List all purchase orders."""
    return db.query(PurchaseOrder).all()


@router.get("/orders/due", response_model=list[PurchaseOrderOut])
def get_due_orders(
    day: int = Query(..., description="Current simulation day"),
    db: Session = Depends(get_db),
) -> list[PurchaseOrderOut]:
    """Return pending orders with expected_delivery_day <= day."""
    return (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.status == "pending",
            PurchaseOrder.expected_delivery_day <= day,
        )
        .all()
    )


@router.put("/orders/{order_id}/deliver", response_model=PurchaseOrderOut)
def deliver_order(
    order_id: int,
    req: DeliverOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    """Mark a purchase order as delivered."""
    po = _get_order_or_404(db, order_id)
    po.actual_delivery_day = req.actual_delivery_day
    po.status = "delivered"
    db.commit()
    db.refresh(po)
    return po


@router.delete("/orders")
def reset_orders(db: Session = Depends(get_db)) -> dict:
    """Delete all purchase orders (used during game import/reset)."""
    count = db.query(PurchaseOrder).delete()
    db.commit()
    return {"deleted": count}


@router.post("/prices/fluctuate")
def fluctuate_prices(db: Session = Depends(get_db)) -> dict:
    """Apply ±10% random price fluctuation to all SupplierProduct.daily_price_factor."""
    products = db.query(SupplierProduct).all()
    for sp in products:
        sp.daily_price_factor = random.uniform(0.90, 1.10)
    db.commit()
    return {"updated": len(products)}
