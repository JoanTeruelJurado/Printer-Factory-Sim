"""Provider FastAPI application.

Endpoints
---------
GET  /api/catalog                        – products with pricing tiers
GET  /api/stock                          – current inventory
POST /api/orders                         – place a purchase order
GET  /api/orders                         – list orders (?status=)
GET  /api/orders/{id}                    – order detail
PUT  /api/catalog/{product_id}/price/{tier_id}  – change a price tier
POST /api/stock/{product_id}/restock     – add to stock
POST /api/day/advance                    – advance simulation day
GET  /api/day/current                    – current simulation day
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from provider_app import schemas
from provider_app.db import get_db, init_db
from provider_app.services import catalog, orders, simulation
from provider_app.services.seed import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = next(get_db())
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Provider App",
    version="1.0.0",
    description=(
        "3D printer parts provider for the supply-chain simulation. "
        "Sells raw materials to manufacturers via a REST API."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _order_to_schema(order) -> schemas.OrderSchema:
    return schemas.OrderSchema(
        id=order.id,
        buyer_name=order.buyer_name,
        product_id=order.product_id,
        product_name=order.product.name,
        quantity=order.quantity,
        unit_price=order.unit_price,
        total_price=order.total_price,
        placed_day=order.placed_day,
        expected_delivery_day=order.expected_delivery_day,
        confirmed_day=order.confirmed_day,
        shipped_day=order.shipped_day,
        delivered_day=order.delivered_day,
        status=order.status,
        created_at=order.created_at,
    )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@app.get("/api/catalog", response_model=list[schemas.ProductSchema], tags=["catalog"])
def get_catalog(db: Session = Depends(get_db)):
    """List all active products with their pricing tiers."""
    return catalog.get_catalog(db)


@app.put(
    "/api/catalog/{product_id}/price/{tier_id}",
    tags=["catalog"],
    summary="Change a pricing tier",
)
def set_price(
    product_id: int,
    tier_id: int,
    req: schemas.SetPriceRequest,
    db: Session = Depends(get_db),
):
    """Update the unit price for a specific tier of a product."""
    try:
        current_day = simulation.get_current_day(db)
        tier = catalog.set_price(db, product_id, tier_id, req.price, current_day)
        return {
            "product_id": product_id,
            "tier_id": tier_id,
            "min_qty": tier.min_qty,
            "max_qty": tier.max_qty,
            "new_price": tier.price_per_unit,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------


@app.get("/api/stock", response_model=list[schemas.StockItemSchema], tags=["stock"])
def get_stock(db: Session = Depends(get_db)):
    """Return current stock levels for all products."""
    stocks = catalog.get_stock(db)
    return [
        schemas.StockItemSchema(
            product_id=s.product_id,
            product_name=s.product.name,
            quantity=s.quantity,
        )
        for s in stocks
    ]


@app.post("/api/stock/{product_id}/restock", tags=["stock"])
def restock(
    product_id: int,
    req: schemas.RestockRequest,
    db: Session = Depends(get_db),
):
    """Add quantity to a product's stock (simulates upstream delivery)."""
    try:
        current_day = simulation.get_current_day(db)
        stock = catalog.restock(db, product_id, req.quantity, current_day)
        return {"product_id": product_id, "new_quantity": stock.quantity}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@app.post("/api/orders", response_model=schemas.OrderSchema, status_code=201, tags=["orders"])
def create_order(req: schemas.CreateOrderRequest, db: Session = Depends(get_db)):
    """Place a purchase order.

    The provider checks the catalog, computes the tier price, sets the
    expected delivery day (current_day + lead_time), and creates the order
    in PENDING state.
    """
    try:
        order = orders.create_order(db, req.buyer, req.product_id, req.quantity)
        return _order_to_schema(order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/orders", response_model=list[schemas.OrderSchema], tags=["orders"])
def list_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all orders, optionally filtered by status."""
    return [_order_to_schema(o) for o in orders.list_orders(db, status)]


@app.get("/api/orders/{order_id}", response_model=schemas.OrderSchema, tags=["orders"])
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Fetch a single order by ID."""
    try:
        return _order_to_schema(orders.get_order(db, order_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Simulation day
# ---------------------------------------------------------------------------


@app.post("/api/day/advance", tags=["simulation"])
def advance_day(db: Session = Depends(get_db)):
    """Advance the simulation by one day.

    Processes all pending → confirmed → shipped → delivered transitions and
    increments the day counter.
    """
    return simulation.advance_day(db)


@app.get("/api/day/current", tags=["simulation"])
def current_day(db: Session = Depends(get_db)):
    """Return the current simulation day number."""
    return {"current_day": simulation.get_current_day(db)}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "app": "provider"}
