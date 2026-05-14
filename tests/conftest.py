"""
Shared test fixtures: in-memory SQLite DB seeded with reference data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import (
    BOM,
    Client,
    Config,
    DailyCosts,
    GameState,
    Inventory,
    Product,
    RawMaterial,
)
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture()
def engine():
    # StaticPool ensures all connections share the same in-memory SQLite database.
    eng = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine):
    """Seeded in-memory DB session, rolled back after each test."""
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    _seed(session)
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(engine):
    """FastAPI TestClient backed by the in-memory DB.

    Patches both the database module's engine/SessionLocal and seed's
    SessionLocal so that startup_event (init_db + seed_initial_data)
    operate on the in-memory test database.
    """
    from unittest.mock import patch

    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.db.database.engine", engine),
        patch("app.db.database.SessionLocal", TestSession),
        patch("app.services.seed.SessionLocal", TestSession),
    ):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed(session) -> None:
    """Insert minimal reference data (idempotent)."""
    if session.query(GameState).filter_by(id=1).first():
        return

    session.add(GameState(
        id=1, current_day=1, wallet_balance=10_000.0,
        warehouse_capacity=10_000, daily_production_capacity=10,
        days_with_negative_balance=0, game_over=False,
    ))
    session.add(DailyCosts(
        id=1, fixed_cost=500.0, variable_cost_per_unit=50.0,
        energy_cost_per_hour=10.0, maintenance_percentage=0.05,
    ))
    session.add(Client(id=1, name="Test Customer"))

    for key, value in {
        "starting_wallet": "10000.0",
        "warehouse_capacity": "10000",
        "daily_production_capacity": "10",
        "capacity_warning_threshold": "0.8",
        "wallet_warning_threshold": "2000.0",
        "wallet_critical_threshold": "500.0",
    }.items():
        session.add(Config(key=key, value=value, description="test"))

    # Products
    hobby = Product(name="Hobby Printer", product_type="finished", sell_price=350.0, assembly_time_hours=2.0)
    session.add(hobby)

    # Materials
    abs_fil = RawMaterial(name="ABS Filament", base_price=25.0, volume_per_unit=1.0)
    motor = RawMaterial(name="Stepper Motor", base_price=18.0, volume_per_unit=1.0)
    board = RawMaterial(name="Control Board", base_price=45.0, volume_per_unit=1.0)
    session.add_all([abs_fil, motor, board])
    session.flush()

    # Inventory (150 units each)
    session.add(Inventory(material_id=abs_fil.id, quantity=150.0, reserved_quantity=0.0))
    session.add(Inventory(material_id=motor.id, quantity=150.0, reserved_quantity=0.0))
    session.add(Inventory(material_id=board.id, quantity=150.0, reserved_quantity=0.0))

    # BOM: Hobby needs 2 ABS + 1 Motor + 1 Board
    session.add(BOM(product_id=hobby.id, material_id=abs_fil.id, qty_needed=2.0))
    session.add(BOM(product_id=hobby.id, material_id=motor.id, qty_needed=1.0))
    session.add(BOM(product_id=hobby.id, material_id=board.id, qty_needed=1.0))

    session.commit()


# ---------------------------------------------------------------------------
# Supplier client mock (autouse — prevents real HTTP calls in all tests)
# ---------------------------------------------------------------------------

_po_counter = [1]


@pytest.fixture(autouse=True)
def mock_supplier_client(monkeypatch):
    """Replace all supplier_client calls with in-process fakes."""
    import app.services.supplier_client as sc

    _po_counter[0] = 1  # reset per test

    def fake_get_suppliers():
        return [{"id": 1, "name": "TestSupplier", "lead_time_days": 2, "reliability": 0.95}]

    def _tiers(base):
        return [
            {"min_quantity": 1,   "unit_price": round(base * 1.00, 2)},
            {"min_quantity": 10,  "unit_price": round(base * 0.90, 2)},
            {"min_quantity": 50,  "unit_price": round(base * 0.82, 2)},
            {"min_quantity": 100, "unit_price": round(base * 0.75, 2)},
        ]

    def fake_get_catalog(supplier_id):
        return {
            "supplier_id": supplier_id,
            "supplier_name": "TestSupplier",
            "lead_time_days": 2,
            "reliability": 0.95,
            "catalog": [
                {"material_id": 1, "material_name": "ABS Filament",
                 "base_unit_cost": 28.0, "daily_price_factor": 1.0, "current_price": 28.0,
                 "stock": 500, "pricing_tiers": _tiers(28.0)},
                {"material_id": 2, "material_name": "Stepper Motor",
                 "base_unit_cost": 20.0, "daily_price_factor": 1.0, "current_price": 20.0,
                 "stock": 500, "pricing_tiers": _tiers(20.0)},
                {"material_id": 3, "material_name": "Control Board",
                 "base_unit_cost": 50.0, "daily_price_factor": 1.0, "current_price": 50.0,
                 "stock": 500, "pricing_tiers": _tiers(50.0)},
            ],
        }

    def fake_get_pricing(supplier_id, material_id, quantity=None):
        prices = {1: ("ABS Filament", 28.0), 2: ("Stepper Motor", 20.0), 3: ("Control Board", 50.0)}
        name, base_price = prices.get(material_id, ("Unknown", 99.0))
        # Apply tier logic: qty >= 100 → 25% discount, qty >= 10 → 10% discount, else base
        if quantity is not None and quantity >= 100:
            unit_price = base_price * 0.75
        elif quantity is not None and quantity >= 10:
            unit_price = base_price * 0.90
        else:
            unit_price = base_price
        return {
            "supplier_id": supplier_id,
            "supplier_name": "TestSupplier",
            "material_id": material_id,
            "material_name": name,
            "base_unit_cost": base_price,
            "daily_price_factor": 1.0,
            "current_price_per_unit": unit_price,
            "lead_time_days": 2,
        }

    def fake_create_order(payload):
        po_id = _po_counter[0]
        _po_counter[0] += 1
        return {
            "id": po_id,
            "supplier_id": payload["supplier_id"],
            "buyer": payload.get("buyer", "factory"),
            "material_id": payload["material_id"],
            "material_name": payload["material_name"],
            "quantity": payload["quantity"],
            "packaging_type": payload.get("packaging_type", "unit"),
            "issue_day": payload["issue_day"],
            "expected_delivery_day": payload["expected_delivery_day"],
            "shipped_day": None,
            "actual_delivery_day": None,
            "status": "pending",
            "unit_cost": payload["unit_cost"],
            "total_cost": payload["total_cost"],
        }

    def fake_get_orders():
        return []

    def fake_get_due_orders(day):
        return []

    def fake_deliver_order(order_id, actual_delivery_day):
        return {"id": order_id, "status": "delivered", "actual_delivery_day": actual_delivery_day}

    def fake_fluctuate_prices():
        pass

    def fake_advance_supplier_day():
        return {"previous_day": 1, "current_day": 2, "delivered_count": 0, "shipped_count": 0}

    def fake_reset_orders():
        return 0

    monkeypatch.setattr(sc, "get_suppliers", fake_get_suppliers)
    monkeypatch.setattr(sc, "get_catalog", fake_get_catalog)
    monkeypatch.setattr(sc, "get_pricing", fake_get_pricing)
    monkeypatch.setattr(sc, "create_order", fake_create_order)
    monkeypatch.setattr(sc, "get_orders", fake_get_orders)
    monkeypatch.setattr(sc, "get_due_orders", fake_get_due_orders)
    monkeypatch.setattr(sc, "deliver_order", fake_deliver_order)
    monkeypatch.setattr(sc, "fluctuate_prices", fake_fluctuate_prices)
    monkeypatch.setattr(sc, "advance_supplier_day", fake_advance_supplier_day)
    monkeypatch.setattr(sc, "reset_orders", fake_reset_orders)
