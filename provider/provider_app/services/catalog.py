"""Catalog and inventory management for the provider."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from provider_app.models import Event, PricingTier, Product, SimulationDay, Stock


def get_catalog(db: Session) -> list[Product]:
    """Return all active products with their pricing tiers."""
    return db.query(Product).filter_by(active=True).all()


def get_product(db: Session, product_id: int) -> Product:
    """Return a single product or raise ValueError."""
    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        raise ValueError(f"Product {product_id} not found")
    return product


def compute_price(db: Session, product_id: int, quantity: int) -> float:
    """Compute unit price for given quantity using tier breaks.

    Tiers are ordered ascending by min_qty.  We find the highest tier whose
    min_qty is <= quantity (and whose max_qty is None or >= quantity).
    """
    tiers = (
        db.query(PricingTier)
        .filter_by(product_id=product_id)
        .order_by(PricingTier.min_qty.desc())
        .all()
    )
    for tier in tiers:
        if quantity >= tier.min_qty:
            if tier.max_qty is None or quantity <= tier.max_qty:
                return tier.price_per_unit
    if tiers:
        # Fallback: cheapest tier (highest min_qty when sorted desc means last)
        return tiers[-1].price_per_unit
    raise ValueError(f"No pricing tiers configured for product {product_id}")


def get_stock(db: Session) -> list[Stock]:
    """Return all stock records with their products loaded."""
    return db.query(Stock).all()


def get_stock_for_product(db: Session, product_id: int) -> int:
    """Return current stock quantity for a product."""
    stock = db.query(Stock).filter_by(product_id=product_id).first()
    return stock.quantity if stock else 0


def restock(db: Session, product_id: int, quantity: int, current_day: int) -> Stock:
    """Add stock for a product (simulated upstream delivery)."""
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    stock = db.query(Stock).filter_by(product_id=product_id).first()
    if not stock:
        # Verify product exists
        get_product(db, product_id)
        stock = Stock(product_id=product_id, quantity=0)
        db.add(stock)
        db.flush()

    stock.quantity += quantity

    db.add(
        Event(
            event_type="stock_updated",
            day=current_day,
            details=json.dumps(
                {
                    "product_id": product_id,
                    "added": quantity,
                    "new_total": stock.quantity,
                }
            ),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(stock)
    return stock


def set_price(
    db: Session,
    product_id: int,
    tier_id: int,
    price: float,
    current_day: int,
) -> PricingTier:
    """Update the price of a specific pricing tier."""
    if price <= 0:
        raise ValueError("Price must be positive")

    tier = db.query(PricingTier).filter_by(id=tier_id, product_id=product_id).first()
    if not tier:
        raise ValueError(f"Pricing tier {tier_id} not found for product {product_id}")

    old_price = tier.price_per_unit
    tier.price_per_unit = price

    db.add(
        Event(
            event_type="price_changed",
            day=current_day,
            details=json.dumps(
                {
                    "product_id": product_id,
                    "tier_id": tier_id,
                    "min_qty": tier.min_qty,
                    "max_qty": tier.max_qty,
                    "old_price": old_price,
                    "new_price": price,
                }
            ),
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    db.refresh(tier)
    return tier
