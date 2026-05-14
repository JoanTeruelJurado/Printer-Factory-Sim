"""Tests for inventory service: reserve, consume, unreserve, availability check."""

import pytest
from app.db.models import Inventory, ManufacturingOrder
from app.services.inventory import (
    check_material_availability,
    consume_materials,
    get_available_quantity,
    reserve_materials,
    unreserve_materials,
)
from app.services.production import create_manufacturing_order, release_manufacturing_order


def _hobby_product_id(db):
    from app.db.models import Product
    return db.query(Product).filter_by(name="Hobby Printer").first().id


def _abs_material_id(db):
    from app.db.models import RawMaterial
    return db.query(RawMaterial).filter_by(name="ABS Filament").first().id


class TestCheckMaterialAvailability:
    def test_enough_stock_returns_fully_available(self, db):
        pid = _hobby_product_id(db)
        result = check_material_availability(db, pid, 5)
        assert result["fully_available"] is True
        assert result["shortages"] == []

    def test_shortage_reported_correctly(self, db):
        # Deplete ABS Filament
        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 1.0  # Hobby needs 2 per unit
        db.flush()

        pid = _hobby_product_id(db)
        result = check_material_availability(db, pid, 2)  # needs 4 ABS total
        assert result["fully_available"] is False
        shortage = next(s for s in result["shortages"] if s["material_id"] == abs_id)
        assert shortage["required"] == 4.0
        assert shortage["available"] == 1.0
        assert shortage["shortage"] == 3.0

    def test_reserved_stock_excluded_from_available(self, db):
        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 10.0
        inv.reserved_quantity = 8.0  # only 2 truly available
        db.flush()

        pid = _hobby_product_id(db)
        # Need 4 ABS (2 units × 2), but only 2 available → shortage
        result = check_material_availability(db, pid, 2)
        assert result["fully_available"] is False

    def test_unknown_product_raises(self, db):
        with pytest.raises(ValueError):
            check_material_availability(db, 9999, 1)


class TestReserveMaterials:
    def test_reserve_increases_reserved_quantity(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 3, 1)
        db.flush()
        reserve_materials(db, mo.id)

        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv.reserved_quantity == 6.0  # 2 ABS × 3 units

    def test_reserve_does_not_change_total_quantity(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 2, 1)
        db.flush()

        abs_id = _abs_material_id(db)
        before = db.query(Inventory).filter_by(material_id=abs_id).first().quantity
        reserve_materials(db, mo.id)
        after = db.query(Inventory).filter_by(material_id=abs_id).first().quantity
        assert before == after

    def test_reserve_insufficient_raises(self, db):
        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 0.0
        db.flush()

        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 1, 1)
        db.flush()

        with pytest.raises(ValueError, match="Insufficient"):
            reserve_materials(db, mo.id)


class TestConsumeMaterials:
    def test_consume_reduces_quantity_and_reserved(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 2, 1)
        db.flush()
        reserve_materials(db, mo.id)

        abs_id = _abs_material_id(db)
        inv_before = db.query(Inventory).filter_by(material_id=abs_id).first()
        qty_before = inv_before.quantity

        consume_materials(db, mo.id, 2)

        inv_after = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv_after.quantity == qty_before - 4.0  # 2 ABS × 2 units
        assert inv_after.reserved_quantity == 0.0


class TestUnreserveMaterials:
    def test_unreserve_restores_available_quantity(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 3, 1)
        db.flush()
        reserve_materials(db, mo.id)

        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv.reserved_quantity == 6.0

        unreserve_materials(db, mo.id)
        assert inv.reserved_quantity == 0.0

    def test_unreserve_does_not_go_below_zero(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 1, 1)
        db.flush()
        # Don't reserve — unreserve should clamp at 0
        unreserve_materials(db, mo.id)
        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv.reserved_quantity == 0.0


class TestGetAvailableQuantity:
    def test_returns_quantity_minus_reserved(self, db):
        abs_id = _abs_material_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 100.0
        inv.reserved_quantity = 30.0
        db.flush()
        assert get_available_quantity(db, abs_id) == 70.0

    def test_missing_material_returns_zero(self, db):
        assert get_available_quantity(db, 9999) == 0.0
