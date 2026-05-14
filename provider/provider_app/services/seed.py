"""Seed the provider database with a plausible starting catalog.

Products are aligned with the manufacturer's bill of materials so orders
between the two apps make sense end-to-end.
"""

from sqlalchemy.orm import Session

from provider_app.db import SessionLocal
from provider_app.models import PricingTier, Product, SimulationDay, Stock


CATALOG: list[dict] = [
    {
        "name": "ABS Filament Spool (1kg)",
        "description": "High-quality ABS filament for FDM 3D printing",
        "lead_time_days": 2,
        "tiers": [(1, 9, 28.0), (10, 49, 24.0), (50, None, 20.0)],
        "stock": 500,
    },
    {
        "name": "PLA Filament Spool (1kg)",
        "description": "Standard PLA filament, easy to print",
        "lead_time_days": 2,
        "tiers": [(1, 9, 25.0), (10, 49, 21.0), (50, None, 17.0)],
        "stock": 500,
    },
    {
        "name": "Aluminum Extrusion 1m",
        "description": "2020 V-slot aluminum profile, 1 m length",
        "lead_time_days": 3,
        "tiers": [(1, 9, 17.0), (10, 49, 14.0), (50, None, 11.0)],
        "stock": 300,
    },
    {
        "name": "Steel Rod 5mm",
        "description": "Precision-ground steel rod, 5 mm diameter × 500 mm",
        "lead_time_days": 2,
        "tiers": [(1, 9, 10.0), (10, 49, 8.0), (50, None, 6.0)],
        "stock": 400,
    },
    {
        "name": "Stepper Motor NEMA17",
        "description": "NEMA17 bipolar stepper, 1.8° step, 40 N·cm holding torque",
        "lead_time_days": 3,
        "tiers": [(1, 9, 21.0), (10, 49, 18.0), (50, None, 14.0)],
        "stock": 300,
    },
    {
        "name": "Linear Rail 200mm",
        "description": "MGN12 linear guide rail with carriage, 200 mm",
        "lead_time_days": 2,
        "tiers": [(1, 9, 14.0), (10, 49, 11.0), (50, None, 9.0)],
        "stock": 400,
    },
    {
        "name": "Control Board v2.1",
        "description": "32-bit 3D printer control board, TMC2209 drivers included",
        "lead_time_days": 4,
        "tiers": [(1, 9, 52.0), (10, 49, 44.0), (50, None, 36.0)],
        "stock": 200,
    },
    {
        "name": "Hotend Assembly",
        "description": "E3D-compatible all-metal hotend with heater block, nozzle, and thermistor",
        "lead_time_days": 3,
        "tiers": [(1, 9, 40.0), (10, 49, 33.0), (50, None, 27.0)],
        "stock": 250,
    },
]


def seed_initial_data(db: Session | None = None) -> None:
    """Populate the database with products, tiers, stock, and simulation day.

    Idempotent: does nothing if SimulationDay id=1 already exists.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        if db.query(SimulationDay).filter_by(id=1).first():
            return  # already seeded

        db.add(SimulationDay(id=1, current_day=1))

        for data in CATALOG:
            product = Product(
                name=data["name"],
                description=data.get("description"),
                lead_time_days=data["lead_time_days"],
                active=True,
            )
            db.add(product)
            db.flush()

            for min_qty, max_qty, price in data["tiers"]:
                db.add(
                    PricingTier(
                        product_id=product.id,
                        min_qty=min_qty,
                        max_qty=max_qty,
                        price_per_unit=price,
                    )
                )

            db.add(Stock(product_id=product.id, quantity=data["stock"]))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()
