from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import (
    BOM,
    Config,
    DailyCosts,
    GameState,
    Inventory,
    Product,
    RawMaterial,
    Supplier,
    SupplierProduct,
    Client,
)


def get_or_create(db: Session, model: Any, defaults: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = {**kwargs}
    if defaults:
        params.update(defaults)
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def seed_initial_data() -> None:
    db = SessionLocal()
    try:
        if db.query(GameState).filter(GameState.id == 1).first() is not None:
            return

        game_state = GameState(
            id=1,
            current_day=1,
            wallet_balance=10000.0,
            warehouse_capacity=10000,
            daily_production_capacity=10,
            days_with_negative_balance=0,
            game_over=False,
        )
        db.add(game_state)

        daily_costs = DailyCosts(
            id=1,
            fixed_cost=500.0,
            variable_cost_per_unit=50.0,
            energy_cost_per_hour=10.0,
            maintenance_percentage=0.05,
        )
        db.add(daily_costs)

        config_values = {
            "starting_wallet": "10000.0",
            "warehouse_capacity": "10000",
            "daily_production_capacity": "10",
            "capacity_warning_threshold": "0.8",
            "wallet_warning_threshold": "2000.0",
            "wallet_critical_threshold": "500.0",
        }
        for key, value in config_values.items():
            db.add(Config(key=key, value=value, description="Auto-populated initial configuration."))

        # Create products
        products = [
            {"name": "Hobby Printer Mini", "product_type": "finished", "sell_price": 350.0, "assembly_time_hours": 2.0},
            {"name": "Prosumer Printer X1", "product_type": "finished", "sell_price": 850.0, "assembly_time_hours": 4.0},
            {"name": "Industrial Printer Pro", "product_type": "finished", "sell_price": 2500.0, "assembly_time_hours": 8.0},
        ]
        product_objects = []
        for product_data in products:
            product = Product(**product_data)
            db.add(product)
            product_objects.append(product)

        # Create raw materials
        materials_data = [
            {"name": "ABS Filament Spool (1kg)", "base_price": 25.0},
            {"name": "PLA Filament Spool (1kg)", "base_price": 22.0},
            {"name": "Aluminum Extrusion 1m", "base_price": 15.0},
            {"name": "Steel Rod 5mm", "base_price": 8.0},
            {"name": "Stepper Motor NEMA17", "base_price": 18.0},
            {"name": "Linear Rail 200mm", "base_price": 12.0},
            {"name": "Control Board v2.1", "base_price": 45.0},
            {"name": "Hotend Assembly", "base_price": 35.0},
        ]
        material_objects = []
        for material_data in materials_data:
            material = RawMaterial(**material_data)
            db.add(material)
            material_objects.append(material)
            db.add(Inventory(material=material, quantity=150.0, reserved_quantity=0.0))

        # Create suppliers
        suppliers_data = [
            {"name": "Industrial Materials Co.", "lead_time_days": 3, "reliability": 0.95},
            {"name": "QuickShip Components", "lead_time_days": 1, "reliability": 0.85},
            {"name": "Global Sourcing Ltd", "lead_time_days": 7, "reliability": 0.98},
        ]
        supplier_objects = []
        for supplier_data in suppliers_data:
            supplier = Supplier(**supplier_data)
            db.add(supplier)
            supplier_objects.append(supplier)

        db.flush()

        # Create BOM (Bill of Materials) for each product
        # Hobby Printer Mini (product_id = 1)
        hobby_bom = [
            (0, 2.0),  # ABS Filament: 2 spools
            (2, 1.0),  # Aluminum Extrusion: 1 piece
            (4, 1.0),  # Stepper Motor: 1 unit
            (5, 2.0),  # Linear Rail: 2 pieces
            (6, 1.0),  # Control Board: 1 unit
        ]
        for material_idx, qty in hobby_bom:
            db.add(BOM(product_id=product_objects[0].id, material_id=material_objects[material_idx].id, qty_needed=qty))

        # Prosumer Printer X1 (product_id = 2)
        prosumer_bom = [
            (0, 3.0),  # ABS Filament: 3 spools
            (1, 2.0),  # PLA Filament: 2 spools
            (2, 4.0),  # Aluminum Extrusion: 4 pieces
            (4, 3.0),  # Stepper Motor: 3 units
            (5, 6.0),  # Linear Rail: 6 pieces
            (6, 1.0),  # Control Board: 1 unit
            (7, 1.0),  # Hotend Assembly: 1 unit
        ]
        for material_idx, qty in prosumer_bom:
            db.add(BOM(product_id=product_objects[1].id, material_id=material_objects[material_idx].id, qty_needed=qty))

        # Industrial Printer Pro (product_id = 3)
        industrial_bom = [
            (0, 5.0),  # ABS Filament: 5 spools
            (1, 3.0),  # PLA Filament: 3 spools
            (2, 8.0),  # Aluminum Extrusion: 8 pieces
            (3, 2.0),  # Steel Rod: 2 pieces
            (4, 5.0),  # Stepper Motor: 5 units
            (5, 8.0),  # Linear Rail: 8 pieces
            (6, 2.0),  # Control Board: 2 units
            (7, 2.0),  # Hotend Assembly: 2 units
        ]
        for material_idx, qty in industrial_bom:
            db.add(BOM(product_id=product_objects[2].id, material_id=material_objects[material_idx].id, qty_needed=qty))

        db.flush()

        # Create Supplier-Material links (SupplierProduct) with pricing
        # Industrial Materials Co. (supplier_id = 1) - Premium, reliable, 3-day lead
        supplier_1_pricing = [
            (0, 28.0),   # ABS Filament: €28
            (1, 25.0),   # PLA Filament: €25
            (2, 17.0),   # Aluminum Extrusion: €17
            (3, 10.0),   # Steel Rod: €10
            (4, 21.0),   # Stepper Motor: €21
            (5, 14.0),   # Linear Rail: €14
            (6, 52.0),   # Control Board: €52
            (7, 40.0),   # Hotend Assembly: €40
        ]
        for material_idx, cost in supplier_1_pricing:
            db.add(SupplierProduct(
                supplier_id=supplier_objects[0].id,
                material_id=material_objects[material_idx].id,
                base_unit_cost=cost,
                daily_price_factor=1.0,
            ))

        # QuickShip Components (supplier_id = 2) - Cheap but unreliable, 1-day lead
        supplier_2_pricing = [
            (0, 22.0),   # ABS Filament: €22
            (1, 19.0),   # PLA Filament: €19
            (2, 12.0),   # Aluminum Extrusion: €12
            (3, 6.0),    # Steel Rod: €6
            (4, 15.0),   # Stepper Motor: €15
            (5, 9.0),    # Linear Rail: €9
            (6, 38.0),   # Control Board: €38
            (7, 28.0),   # Hotend Assembly: €28
        ]
        for material_idx, cost in supplier_2_pricing:
            db.add(SupplierProduct(
                supplier_id=supplier_objects[1].id,
                material_id=material_objects[material_idx].id,
                base_unit_cost=cost,
                daily_price_factor=1.0,
            ))

        # Global Sourcing Ltd (supplier_id = 3) - Mid-range, very reliable, 7-day lead
        supplier_3_pricing = [
            (0, 25.0),   # ABS Filament: €25
            (1, 22.0),   # PLA Filament: €22
            (2, 15.0),   # Aluminum Extrusion: €15
            (3, 8.0),    # Steel Rod: €8
            (4, 18.0),   # Stepper Motor: €18
            (5, 12.0),   # Linear Rail: €12
            (6, 45.0),   # Control Board: €45
            (7, 35.0),   # Hotend Assembly: €35
        ]
        for material_idx, cost in supplier_3_pricing:
            db.add(SupplierProduct(
                supplier_id=supplier_objects[2].id,
                material_id=material_objects[material_idx].id,
                base_unit_cost=cost,
                daily_price_factor=1.0,
            ))

        db.commit()
    except IntegrityError as e:
        db.rollback()
        print(f"Seed data already exists or integrity error: {e}")
    finally:
        db.close()


from datetime import datetime

from app.db.models import DemandOrder, Event, ManufacturingOrder, PurchaseOrder


def reset_game(db: Session) -> None:
    game_state = db.query(GameState).filter(GameState.id == 1).first()
    if game_state is None:
        raise ValueError("Game state does not exist")

    # Clear all transactional data
    db.query(DemandOrder).delete()
    db.query(ManufacturingOrder).delete()
    db.query(PurchaseOrder).delete()
    db.query(Event).delete()

    # Reset inventory to 150 units each
    for inv in db.query(Inventory).all():
        inv.quantity = 150.0
        inv.reserved_quantity = 0.0

    # Reset game state
    game_state.current_day = 1
    game_state.wallet_balance = 10000.0
    game_state.days_with_negative_balance = 0
    game_state.game_over = False
    game_state.last_updated = datetime.utcnow()

    db.commit()
