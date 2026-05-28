"""
Supplier API route handlers.

Inter-service endpoints (called by Factory API):
  GET  /suppliers                          — list all suppliers
  GET  /suppliers/{id}/catalog             — catalog with current prices
  GET  /suppliers/{id}/pricing/{mat_id}    — single material pricing
  POST /orders                             — create purchase order (factory flow)
  GET  /orders                             — list all purchase orders
  GET  /orders/due                         — shipped orders ready for factory delivery
  PUT  /orders/{id}/deliver                — mark order as delivered
  POST /prices/fluctuate                   — apply ±10% price fluctuation
  DELETE /orders                           — delete all orders (reset/import)
  GET  /health                             — health check

CLI / standalone endpoints (human/agent use):
  GET  /api/catalog                        — all products with pricing tiers
  GET  /api/stock                          — current stock levels
  POST /api/orders                         — place order (stock check + tier pricing)
  GET  /api/orders                         — list all orders
  GET  /api/orders/{id}                    — single order detail
  POST /api/stock/{sp_id}/restock         — add to supplier stock
  PUT  /api/pricing/tiers/{tier_id}       — update a pricing tier
  POST /api/day/advance                    — advance simulation day, ship due orders
  GET  /api/day/current                    — current simulation day
  GET  /api/metrics                        — provider metrics history
  GET  /api/events                         — supplier event log (last 200)
  GET  /api/export                         — JSON snapshot export
  POST /api/import                         — restore from JSON snapshot
"""

import json
import random
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supplier_api.database import get_db
from supplier_api.models import (
    PricingTier,
    ProviderMetrics,
    PurchaseOrder,
    SimState,
    Stock,
    Supplier,
    SupplierEvent,
    SupplierProduct,
)

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class SupplierOut(BaseModel):
    id: int
    name: str
    lead_time_days: int
    reliability: float

    class Config:
        from_attributes = True


class TierOut(BaseModel):
    min_quantity: int
    unit_price: float


class CatalogItemOut(BaseModel):
    material_id: int
    material_name: str
    base_unit_cost: float
    daily_price_factor: float
    current_price: float
    stock: int
    pricing_tiers: list[TierOut]

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
    """Used by the factory inter-service call (prices pre-computed)."""
    supplier_id: int
    buyer: str = "factory"
    material_id: int
    material_name: str
    quantity: int
    packaging_type: str = "unit"
    issue_day: int
    unit_cost: float
    total_cost: float
    expected_delivery_day: int


class PlaceOrderRequest(BaseModel):
    """Used by CLI / external agents (provider computes price and delivery day)."""
    supplier_id: int
    material_id: int
    quantity: int
    buyer: str = "Manufacturer"


class DeliverOrderRequest(BaseModel):
    actual_delivery_day: int


class RestockRequest(BaseModel):
    quantity: int


class UpdateTierRequest(BaseModel):
    unit_price: float


class PurchaseOrderOut(BaseModel):
    id: int
    supplier_id: int
    buyer: str | None
    material_id: int
    material_name: str
    quantity: int
    packaging_type: str
    issue_day: int
    expected_delivery_day: int
    shipped_day: int | None
    actual_delivery_day: int | None
    status: str
    unit_cost: float
    total_cost: float

    class Config:
        from_attributes = True


class PricingTierOut(BaseModel):
    id: int
    min_quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class CatalogEntryOut(BaseModel):
    supplier_product_id: int
    supplier_id: int
    supplier_name: str
    material_id: int
    material_name: str
    lead_time_days: int
    base_unit_cost: float
    daily_price_factor: float
    stock: int
    pricing_tiers: list[PricingTierOut]


class StockItemOut(BaseModel):
    supplier_product_id: int
    supplier_id: int
    supplier_name: str
    material_id: int
    material_name: str
    quantity: int


class DayOut(BaseModel):
    current_day: int


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _get_sim_day(db: Session) -> int:
    row = db.query(SimState).filter_by(key="current_day").first()
    if row is None:
        # Auto-initialise if missing
        row = SimState(key="current_day", value="1")
        db.add(row)
        db.commit()
    return int(row.value)


def _set_sim_day(db: Session, day: int) -> None:
    row = db.query(SimState).filter_by(key="current_day").first()
    if row is None:
        db.add(SimState(key="current_day", value=str(day)))
    else:
        row.value = str(day)


def _compute_tier_price(tiers: list[PricingTier], quantity: int) -> float:
    """Return the unit price for the highest tier the quantity qualifies for."""
    applicable = [t for t in tiers if quantity >= t.min_quantity]
    if not applicable:
        # Fallback: use the lowest tier
        return min(tiers, key=lambda t: t.min_quantity).unit_price if tiers else 0.0
    return max(applicable, key=lambda t: t.min_quantity).unit_price


def _log_event(
    db: Session,
    sim_day: int,
    event_type: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(SupplierEvent(
        sim_day=sim_day,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=json.dumps(detail) if detail else None,
        created_at=datetime.utcnow(),
    ))


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "supplier-api"}


# ══════════════════════════════════════════════════════════════════════════════
# Inter-service endpoints (Factory API ↔ Supplier API)
# ══════════════════════════════════════════════════════════════════════════════

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
        tiers = sorted(sp.pricing_tiers, key=lambda t: t.min_quantity)
        catalog.append(CatalogItemOut(
            material_id=sp.material_id,
            material_name=sp.material_name,
            base_unit_cost=sp.base_unit_cost,
            daily_price_factor=sp.daily_price_factor,
            current_price=sp.base_unit_cost * sp.daily_price_factor,
            stock=sp.stock.quantity if sp.stock else 0,
            pricing_tiers=[TierOut(min_quantity=t.min_quantity, unit_price=t.unit_price) for t in tiers],
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
    quantity: int | None = Query(default=None, description="Quantity to apply volume tier pricing"),
    db: Session = Depends(get_db),
) -> MaterialPricingOut:
    """Get pricing for a specific material from a supplier.

    If *quantity* is provided, the returned ``current_price_per_unit`` reflects
    the applicable volume-discount tier (multiplied by the daily price factor).
    Without *quantity*, the base price × daily factor is returned.
    """
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

    if quantity is not None and sp.pricing_tiers:
        tier_price = _compute_tier_price(sp.pricing_tiers, quantity)
        current_price = tier_price * sp.daily_price_factor
    else:
        current_price = sp.base_unit_cost * sp.daily_price_factor

    return MaterialPricingOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        material_id=sp.material_id,
        material_name=sp.material_name,
        base_unit_cost=sp.base_unit_cost,
        daily_price_factor=sp.daily_price_factor,
        current_price_per_unit=current_price,
        lead_time_days=supplier.lead_time_days,
    )


@router.post("/orders", response_model=PurchaseOrderOut, status_code=201)
def create_order_interservice(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    """Create a purchase order (factory inter-service flow, prices pre-computed)."""
    _get_supplier_or_404(db, req.supplier_id)

    # Deduct stock
    sp = db.query(SupplierProduct).filter_by(
        supplier_id=req.supplier_id, material_id=req.material_id
    ).first()
    if sp and sp.stock:
        if sp.stock.quantity < req.quantity:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient supplier stock: requested {req.quantity}, available {sp.stock.quantity}",
            )
        sp.stock.quantity -= req.quantity

    po = PurchaseOrder(
        supplier_id=req.supplier_id,
        buyer=req.buyer,
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
    db.flush()

    sim_day = _get_sim_day(db)
    _log_event(db, sim_day, "order_placed", "purchase_order", po.id, {
        "buyer": po.buyer,
        "supplier_id": po.supplier_id,
        "material_id": po.material_id,
        "quantity": po.quantity,
        "total_cost": po.total_cost,
        "expected_delivery_day": po.expected_delivery_day,
        "source": "factory",
    })

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
    """Return orders with status='delivered' pending factory acknowledgement."""
    return (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status == "delivered")
        .all()
    )


@router.put("/orders/{order_id}/deliver", response_model=PurchaseOrderOut)
def deliver_order(
    order_id: int,
    req: DeliverOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    """Factory acknowledges receipt of a delivered order (transitions delivered → received)."""
    po = _get_order_or_404(db, order_id)
    po.actual_delivery_day = req.actual_delivery_day
    po.status = "received"

    sim_day = _get_sim_day(db)
    _log_event(db, sim_day, "order_received", "purchase_order", po.id, {
        "buyer": po.buyer,
        "material_id": po.material_id,
        "quantity": po.quantity,
        "actual_delivery_day": po.actual_delivery_day,
    })

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

    sim_day = _get_sim_day(db)
    _log_event(db, sim_day, "price_changed", detail={"updated": len(products)})

    db.commit()
    return {"updated": len(products)}


# ══════════════════════════════════════════════════════════════════════════════
# CLI / standalone endpoints  (/api/*)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/catalog", response_model=list[CatalogEntryOut])
def api_catalog(db: Session = Depends(get_db)) -> list[CatalogEntryOut]:
    """Full catalog of all products across all suppliers, including pricing tiers and stock."""
    entries = []
    supplier_products = db.query(SupplierProduct).all()
    for sp in supplier_products:
        stock_qty = sp.stock.quantity if sp.stock else 0
        tiers = sorted(sp.pricing_tiers, key=lambda t: t.min_quantity)
        entries.append(CatalogEntryOut(
            supplier_product_id=sp.id,
            supplier_id=sp.supplier_id,
            supplier_name=sp.supplier.name,
            material_id=sp.material_id,
            material_name=sp.material_name,
            lead_time_days=sp.supplier.lead_time_days,
            base_unit_cost=sp.base_unit_cost,
            daily_price_factor=sp.daily_price_factor,
            stock=stock_qty,
            pricing_tiers=[
                PricingTierOut(id=t.id, min_quantity=t.min_quantity, unit_price=t.unit_price)
                for t in tiers
            ],
        ))
    return entries


@router.get("/api/stock", response_model=list[StockItemOut])
def api_stock(db: Session = Depends(get_db)) -> list[StockItemOut]:
    """Current stock levels for all supplier-product combinations."""
    stocks = db.query(Stock).all()
    result = []
    for s in stocks:
        sp = s.supplier_product
        result.append(StockItemOut(
            supplier_product_id=sp.id,
            supplier_id=sp.supplier_id,
            supplier_name=sp.supplier.name,
            material_id=sp.material_id,
            material_name=sp.material_name,
            quantity=s.quantity,
        ))
    return result


@router.post("/api/orders", response_model=PurchaseOrderOut, status_code=201)
def api_place_order(
    req: PlaceOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderOut:
    """Place a purchase order via CLI/agent. Provider checks stock and computes tier price."""
    supplier = _get_supplier_or_404(db, req.supplier_id)

    sp = (
        db.query(SupplierProduct)
        .filter_by(supplier_id=req.supplier_id, material_id=req.material_id)
        .first()
    )
    if not sp:
        raise HTTPException(
            status_code=404,
            detail=f"Material {req.material_id} not available from supplier {req.supplier_id}",
        )

    # Check stock
    stock = sp.stock
    if stock is None or stock.quantity < req.quantity:
        available = stock.quantity if stock else 0
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient stock: requested {req.quantity}, available {available}",
        )

    # Compute tier price
    unit_price = _compute_tier_price(sp.pricing_tiers, req.quantity)
    total_cost = round(unit_price * req.quantity, 2)

    # Compute delivery day
    sim_day = _get_sim_day(db)
    expected_delivery_day = sim_day + supplier.lead_time_days

    # Deduct stock
    stock.quantity -= req.quantity

    po = PurchaseOrder(
        supplier_id=req.supplier_id,
        buyer=req.buyer,
        material_id=req.material_id,
        material_name=sp.material_name,
        quantity=req.quantity,
        packaging_type="unit",
        issue_day=sim_day,
        expected_delivery_day=expected_delivery_day,
        status="pending",
        unit_cost=unit_price,
        total_cost=total_cost,
    )
    db.add(po)
    db.flush()

    _log_event(db, sim_day, "order_placed", "purchase_order", po.id, {
        "buyer": req.buyer,
        "supplier_id": req.supplier_id,
        "material_id": req.material_id,
        "quantity": req.quantity,
        "unit_price": unit_price,
        "total_cost": total_cost,
        "expected_delivery_day": expected_delivery_day,
        "source": "cli",
    })
    _log_event(db, sim_day, "stock_updated", "supplier_product", sp.id, {
        "material_id": sp.material_id,
        "delta": -req.quantity,
        "remaining": stock.quantity,
    })

    db.commit()
    db.refresh(po)
    return po


@router.get("/api/orders", response_model=list[PurchaseOrderOut])
def api_list_orders(
    status: str | None = Query(default=None, description="Filter by status"),
    db: Session = Depends(get_db),
) -> list[PurchaseOrderOut]:
    """List all purchase orders, optionally filtered by status."""
    q = db.query(PurchaseOrder)
    if status:
        q = q.filter(PurchaseOrder.status == status)
    return q.order_by(PurchaseOrder.id.desc()).all()


@router.get("/api/orders/{order_id}", response_model=PurchaseOrderOut)
def api_get_order(order_id: int, db: Session = Depends(get_db)) -> PurchaseOrderOut:
    """Get details of a single purchase order."""
    return _get_order_or_404(db, order_id)


@router.post("/api/stock/{supplier_product_id}/restock")
def api_restock(
    supplier_product_id: int,
    req: RestockRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Add quantity to a supplier's own stock (simulated upstream replenishment)."""
    sp = db.query(SupplierProduct).filter_by(id=supplier_product_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail=f"SupplierProduct {supplier_product_id} not found")
    if req.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be positive")

    stock = sp.stock
    if stock is None:
        stock = Stock(supplier_product_id=sp.id, quantity=0)
        db.add(stock)
        db.flush()

    stock.quantity += req.quantity

    sim_day = _get_sim_day(db)
    _log_event(db, sim_day, "stock_updated", "supplier_product", sp.id, {
        "material_id": sp.material_id,
        "delta": req.quantity,
        "new_total": stock.quantity,
    })

    db.commit()
    return {
        "supplier_product_id": sp.id,
        "material_name": sp.material_name,
        "new_quantity": stock.quantity,
    }


@router.put("/api/pricing/tiers/{tier_id}")
def api_update_tier(
    tier_id: int,
    req: UpdateTierRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Update the unit price for a specific pricing tier."""
    tier = db.query(PricingTier).filter_by(id=tier_id).first()
    if not tier:
        raise HTTPException(status_code=404, detail=f"Pricing tier {tier_id} not found")
    if req.unit_price <= 0:
        raise HTTPException(status_code=422, detail="unit_price must be positive")

    old_price = tier.unit_price
    tier.unit_price = req.unit_price

    sim_day = _get_sim_day(db)
    _log_event(db, sim_day, "price_changed", "pricing_tier", tier_id, {
        "supplier_product_id": tier.supplier_product_id,
        "min_quantity": tier.min_quantity,
        "old_price": old_price,
        "new_price": req.unit_price,
    })

    db.commit()
    return {
        "tier_id": tier_id,
        "min_quantity": tier.min_quantity,
        "old_price": old_price,
        "new_price": req.unit_price,
    }


@router.post("/api/day/advance")
def api_advance_day(db: Session = Depends(get_db)) -> dict:
    """
    Advance the supplier's simulation day by one.

    Step 1 — shipped → delivered:
      Orders already in 'shipped' state with expected_delivery_day <= current_day
      are marked 'delivered' (goods have physically arrived at the buyer).

    Step 2 — pending → shipped:
      Pending orders with expected_delivery_day <= current_day are dispatched:
      stock is checked and deducted, order marked 'shipped'.

    Step 3 — increment current_day.

    Every transition writes to the supplier_events table.
    """
    current_day = _get_sim_day(db)

    # ── Step 1: pending → shipped ─────────────────────────────────────────────
    # All pending orders are dispatched (shipped) immediately when the provider
    # processes the day. The expected_delivery_day controls WHEN they arrive,
    # not when they are sent.
    pending_orders = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status == "pending")
        .all()
    )
    shipped = []
    for po in pending_orders:
        po.status = "shipped"
        po.shipped_day = current_day
        _log_event(db, current_day, "order_shipped", "purchase_order", po.id, {
            "buyer": po.buyer,
            "material_id": po.material_id,
            "material_name": po.material_name,
            "quantity": po.quantity,
            "shipped_day": current_day,
            "expected_delivery_day": po.expected_delivery_day,
        })
        shipped.append(po.id)

    # ── Step 2: shipped/delayed → delivered (with reliability check) ──────────
    # Orders due today (shipped or previously delayed) go through a reliability
    # roll. On success they become 'delivered'; on failure they become 'delayed'
    # with a new expected_delivery_day 1–3 days ahead.
    due_orders = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.status.in_(["shipped", "delayed"]),
            PurchaseOrder.expected_delivery_day <= current_day,
        )
        .all()
    )
    delivered = []
    delayed_orders = []
    for po in due_orders:
        supplier = db.query(Supplier).filter_by(id=po.supplier_id).first()
        reliability = supplier.reliability if supplier else 1.0

        if random.random() < reliability:
            po.status = "delivered"
            po.actual_delivery_day = current_day
            _log_event(db, current_day, "order_delivered", "purchase_order", po.id, {
                "buyer": po.buyer,
                "material_id": po.material_id,
                "material_name": po.material_name,
                "quantity": po.quantity,
                "actual_delivery_day": current_day,
            })
            delivered.append(po.id)
        else:
            delay_days = random.randint(1, 3)
            new_delivery_day = current_day + delay_days
            po.status = "delayed"
            po.expected_delivery_day = new_delivery_day
            _log_event(db, current_day, "order_delayed", "purchase_order", po.id, {
                "buyer": po.buyer,
                "material_id": po.material_id,
                "material_name": po.material_name,
                "quantity": po.quantity,
                "reliability": reliability,
                "new_expected_delivery_day": new_delivery_day,
            })
            delayed_orders.append(po.id)

    # ── Step 3: replenish supplier stock ──────────────────────────────────────
    # Each supplier_product restores up to 15 units/day, capped at 500.
    REPLENISH_PER_DAY = 15
    MAX_STOCK = 500
    for stock in db.query(Stock).all():
        stock.quantity = min(stock.quantity + REPLENISH_PER_DAY, MAX_STOCK)

    # ── Step 4: increment day ─────────────────────────────────────────────────
    new_day = current_day + 1
    _set_sim_day(db, new_day)

    _log_event(db, current_day, "day_advanced", detail={
        "from_day": current_day,
        "to_day": new_day,
        "orders_delivered": delivered,
        "orders_shipped": shipped,
        "orders_delayed": delayed_orders,
    })

    # ── Step 5: snapshot metrics ─────────────────────────────────────────
    stock_snap = {}
    price_snap = {}
    for sp in db.query(SupplierProduct).all():
        st = db.query(Stock).filter_by(supplier_product_id=sp.id).first()
        stock_snap[sp.material_name] = st.quantity if st else 0
        top_tier = (
            db.query(PricingTier)
            .filter_by(supplier_product_id=sp.id)
            .order_by(PricingTier.min_quantity.desc())
            .first()
        )
        price_snap[sp.material_name] = top_tier.unit_price if top_tier else sp.base_unit_cost

    pending_count = db.query(PurchaseOrder).filter(PurchaseOrder.status == "pending").count()
    shipped_count = db.query(PurchaseOrder).filter(PurchaseOrder.status == "shipped").count()
    delivered_count = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(["delivered", "received"])).count()

    db.add(ProviderMetrics(
        sim_day=current_day,
        stock_json=json.dumps(stock_snap),
        price_json=json.dumps(price_snap),
        orders_pending=pending_count,
        orders_shipped=shipped_count,
        orders_delivered=delivered_count,
    ))

    db.commit()
    return {
        "previous_day": current_day,
        "current_day": new_day,
        "orders_delivered": delivered,
        "delivered_count": len(delivered),
        "orders_shipped": shipped,
        "shipped_count": len(shipped),
        "orders_delayed": delayed_orders,
        "delayed_count": len(delayed_orders),
    }


@router.get("/api/day/current", response_model=DayOut)
def api_current_day(db: Session = Depends(get_db)) -> DayOut:
    """Return the supplier's current simulation day."""
    return DayOut(current_day=_get_sim_day(db))


@router.get("/api/metrics")
def api_metrics(db: Session = Depends(get_db)) -> list[dict]:
    """Return all provider metrics rows ordered by sim_day."""
    rows = db.query(ProviderMetrics).order_by(ProviderMetrics.sim_day).all()
    return [
        {
            "sim_day": r.sim_day,
            "stock_json": r.stock_json,
            "price_json": r.price_json,
            "orders_pending": r.orders_pending,
            "orders_shipped": r.orders_shipped,
            "orders_delivered": r.orders_delivered,
        }
        for r in rows
    ]


@router.get("/api/events")
def api_events(
    sim_day: int | None = Query(default=None, description="Filter events by simulation day"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the last 200 supplier events in chronological order."""
    q = db.query(SupplierEvent)
    if sim_day is not None:
        q = q.filter(SupplierEvent.sim_day == sim_day)
    rows = q.order_by(SupplierEvent.id.desc()).limit(200).all()
    rows.reverse()
    return [
        {
            "id": e.id,
            "sim_day": e.sim_day,
            "event_type": e.event_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "detail": e.detail,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


@router.get("/api/export")
def api_export(db: Session = Depends(get_db)) -> dict:
    """Export full supplier state as a JSON snapshot."""
    current_day = _get_sim_day(db)

    suppliers = db.query(Supplier).all()
    supplier_products = db.query(SupplierProduct).all()
    tiers = db.query(PricingTier).all()
    stocks = db.query(Stock).all()
    orders = db.query(PurchaseOrder).all()
    events = db.query(SupplierEvent).all()

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "sim_state": {"current_day": current_day},
        "suppliers": [
            {"id": s.id, "name": s.name, "lead_time_days": s.lead_time_days, "reliability": s.reliability}
            for s in suppliers
        ],
        "supplier_products": [
            {
                "id": sp.id, "supplier_id": sp.supplier_id,
                "material_id": sp.material_id, "material_name": sp.material_name,
                "base_unit_cost": sp.base_unit_cost, "daily_price_factor": sp.daily_price_factor,
            }
            for sp in supplier_products
        ],
        "pricing_tiers": [
            {"id": t.id, "supplier_product_id": t.supplier_product_id,
             "min_quantity": t.min_quantity, "unit_price": t.unit_price}
            for t in tiers
        ],
        "stock": [
            {"supplier_product_id": s.supplier_product_id, "quantity": s.quantity}
            for s in stocks
        ],
        "purchase_orders": [
            {
                "id": po.id, "supplier_id": po.supplier_id,
                "material_id": po.material_id, "material_name": po.material_name,
                "quantity": po.quantity, "packaging_type": po.packaging_type,
                "issue_day": po.issue_day, "expected_delivery_day": po.expected_delivery_day,
                "shipped_day": po.shipped_day, "actual_delivery_day": po.actual_delivery_day,
                "status": po.status, "unit_cost": po.unit_cost, "total_cost": po.total_cost,
            }
            for po in orders
        ],
        "events": [
            {
                "id": e.id, "sim_day": e.sim_day, "event_type": e.event_type,
                "entity_type": e.entity_type, "entity_id": e.entity_id,
                "detail": e.detail, "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.post("/api/import")
def api_import(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """Restore supplier state from a JSON snapshot."""
    required = {"sim_state", "purchase_orders"}
    if not required.issubset(payload.keys()):
        raise HTTPException(status_code=422, detail=f"Missing keys: {required - payload.keys()}")

    try:
        # Wipe transactional data
        db.query(SupplierEvent).delete()
        db.query(PurchaseOrder).delete()
        db.flush()

        # Restore sim state
        _set_sim_day(db, payload["sim_state"]["current_day"])

        # Restore purchase orders
        for po_data in payload["purchase_orders"]:
            db.add(PurchaseOrder(
                id=po_data["id"],
                supplier_id=po_data["supplier_id"],
                material_id=po_data["material_id"],
                material_name=po_data.get("material_name", str(po_data["material_id"])),
                quantity=po_data["quantity"],
                packaging_type=po_data.get("packaging_type", "unit"),
                issue_day=po_data["issue_day"],
                expected_delivery_day=po_data["expected_delivery_day"],
                shipped_day=po_data.get("shipped_day"),
                actual_delivery_day=po_data.get("actual_delivery_day"),
                status=po_data["status"],
                unit_cost=po_data["unit_cost"],
                total_cost=po_data["total_cost"],
            ))

        # Restore stock if provided
        for stock_data in payload.get("stock", []):
            stock = db.query(Stock).filter_by(
                supplier_product_id=stock_data["supplier_product_id"]
            ).first()
            if stock:
                stock.quantity = stock_data["quantity"]

        db.commit()
        return {"success": True, "message": f"Imported at day {payload['sim_state']['current_day']}"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
