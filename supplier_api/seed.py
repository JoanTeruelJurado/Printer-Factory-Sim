"""
Seed data for the Supplier API.

Seeds 3 suppliers, 8 materials, 24 SupplierProduct links, pricing tiers
(3 per product), stock (500 units per product), and sim_state (day=1).
"""

from sqlalchemy.exc import IntegrityError

from supplier_api.database import SessionLocal
from supplier_api.models import PricingTier, SimState, Stock, Supplier, SupplierProduct


def seed_supplier_data() -> None:
    """Seed suppliers and supplier-product catalog if not already present."""
    db = SessionLocal()
    try:
        # Idempotency guard: skip if suppliers already exist
        if db.query(Supplier).first() is not None:
            return

        # ── Suppliers ──────────────────────────────────────────────────────────
        suppliers_data = [
            {"name": "Industrial Materials Co.", "lead_time_days": 3, "reliability": 0.95},
            {"name": "QuickShip Components",     "lead_time_days": 1, "reliability": 0.85},
            {"name": "Global Sourcing Ltd",      "lead_time_days": 7, "reliability": 0.98},
        ]
        supplier_objects = []
        for data in suppliers_data:
            s = Supplier(**data)
            db.add(s)
            supplier_objects.append(s)

        db.flush()

        # ── Material metadata (id matches factory raw_materials ids) ──────────
        materials = [
            (1, "ABS Filament Spool (1kg)"),
            (2, "PLA Filament Spool (1kg)"),
            (3, "Aluminum Extrusion 1m"),
            (4, "Steel Rod 5mm"),
            (5, "Stepper Motor NEMA17"),
            (6, "Linear Rail 200mm"),
            (7, "Control Board v2.1"),
            (8, "Hotend Assembly"),
        ]

        # ── Base prices per supplier ───────────────────────────────────────────
        # Industrial Materials Co. — premium pricing
        supplier_1_pricing = [28.0, 25.0, 17.0, 10.0, 21.0, 14.0, 52.0, 40.0]
        # QuickShip Components — cheapest pricing
        supplier_2_pricing = [22.0, 19.0, 12.0,  6.0, 15.0,  9.0, 38.0, 28.0]
        # Global Sourcing Ltd — mid-range pricing
        supplier_3_pricing = [25.0, 22.0, 15.0,  8.0, 18.0, 12.0, 45.0, 35.0]

        all_pricing = [supplier_1_pricing, supplier_2_pricing, supplier_3_pricing]

        for supplier_obj, pricing in zip(supplier_objects, all_pricing):
            for (mat_id, mat_name), base_cost in zip(materials, pricing):
                sp = SupplierProduct(
                    supplier_id=supplier_obj.id,
                    material_id=mat_id,
                    material_name=mat_name,
                    base_unit_cost=base_cost,
                    daily_price_factor=1.0,
                )
                db.add(sp)
                db.flush()

                # ── Pricing tiers (4 per product) ──────────────────────────────
                # Tier 1:  1-9   units → base price (matches catalog)
                # Tier 2: 10-49  units → 10% discount
                # Tier 3: 50-99  units → 18% discount
                # Tier 4: 100+   units → 25% discount
                db.add(PricingTier(
                    supplier_product_id=sp.id,
                    min_quantity=1,
                    unit_price=round(base_cost * 1.00, 2),
                ))
                db.add(PricingTier(
                    supplier_product_id=sp.id,
                    min_quantity=10,
                    unit_price=round(base_cost * 0.90, 2),
                ))
                db.add(PricingTier(
                    supplier_product_id=sp.id,
                    min_quantity=50,
                    unit_price=round(base_cost * 0.82, 2),
                ))
                db.add(PricingTier(
                    supplier_product_id=sp.id,
                    min_quantity=100,
                    unit_price=round(base_cost * 0.75, 2),
                ))

                # ── Initial stock (500 units per product) ──────────────────────
                db.add(Stock(supplier_product_id=sp.id, quantity=500))

        # ── Simulation state ───────────────────────────────────────────────────
        if db.query(SimState).filter_by(key="current_day").first() is None:
            db.add(SimState(key="current_day", value="1"))

        db.commit()
    except IntegrityError as e:
        db.rollback()
        print(f"Supplier seed data already exists or integrity error: {e}")
    finally:
        db.close()
