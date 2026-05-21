"""
Seed data for the Retailer App.

Seeds game state, product catalog, and initial stock levels.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailer.database import SessionLocal
from retailer.models import Catalog, RetailerGameState, RetailerStock


def seed_retailer_data(db: Session | None = None) -> None:
    """Seed retailer catalog and initial stock if not already present.

    If *db* is None a new session is created and closed automatically
    (mirrors the supplier_api pattern for startup seeding).
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        # Idempotency guard: skip if catalog already exists
        if db.query(Catalog).first() is not None:
            return

        # ── Game state (singleton, id=1) ─────────────────────────────────────
        if db.query(RetailerGameState).filter_by(id=1).first() is None:
            db.add(RetailerGameState(id=1, current_day=1, wallet_balance=50000.0))

        # ── Product catalog ──────────────────────────────────────────────────
        catalog_items = [
            Catalog(
                model_name="P3D-Classic",
                description="Entry-level 3D printer with heated bed and PLA/ABS support.",
                retail_price=390.0,
                wholesale_price=300.0,
            ),
            Catalog(
                model_name="P3D-Pro",
                description="Professional 3D printer with dual extruder and auto-leveling.",
                retail_price=520.0,
                wholesale_price=400.0,
            ),
        ]
        for item in catalog_items:
            db.add(item)

        db.flush()

        # ── Initial stock (10 units per model) ──────────────────────────────
        for item in catalog_items:
            db.add(RetailerStock(model_name=item.model_name, quantity_on_hand=10))

        db.commit()
    except IntegrityError as e:
        db.rollback()
        print(f"Retailer seed data already exists or integrity error: {e}")
    finally:
        if own_session:
            db.close()


def reset_retailer(db: Session | None = None) -> None:
    """Wipe all retailer data and re-seed from scratch.

    If *db* is None a new session is created and closed automatically.
    """
    from retailer.models import (
        Catalog,
        CustomerOrder,
        RetailerEvent,
        RetailerGameState,
        RetailerPurchaseOrder,
        RetailerStock,
    )

    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        # Delete in dependency-safe order
        db.query(RetailerEvent).delete()
        db.query(CustomerOrder).delete()
        db.query(RetailerPurchaseOrder).delete()
        db.query(RetailerStock).delete()
        db.query(Catalog).delete()
        db.query(RetailerGameState).delete()
        db.commit()

        # Re-seed
        seed_retailer_data(db)
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()
