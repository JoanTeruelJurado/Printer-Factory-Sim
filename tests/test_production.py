"""Tests for production service: create, release (full + partial), cancel."""

import pytest
from app.db.models import Inventory, ManufacturingOrder
from app.services.production import (
    ProductionError,
    cancel_manufacturing_order,
    create_manufacturing_order,
    release_manufacturing_order,
)


def _hobby_product_id(db):
    from app.db.models import Product
    return db.query(Product).filter_by(name="Hobby Printer").first().id


def _abs_id(db):
    from app.db.models import RawMaterial
    return db.query(RawMaterial).filter_by(name="ABS Filament").first().id


class TestCreateManufacturingOrder:
    def test_creates_pending_order(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 5, 1)
        assert mo.status == "pending"
        assert mo.quantity == 5
        assert mo.remaining_qty == 5
        assert mo.created_day == 1

    def test_zero_quantity_raises(self, db):
        pid = _hobby_product_id(db)
        with pytest.raises(ProductionError):
            create_manufacturing_order(db, pid, 0, 1)

    def test_unknown_product_raises(self, db):
        with pytest.raises(ProductionError):
            create_manufacturing_order(db, 9999, 1, 1)


class TestReleaseManufacturingOrderFull:
    def test_full_release_changes_status_to_released(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 4, 1)
        db.flush()
        released = release_manufacturing_order(db, mo.id, 4)
        assert released.status == "released"
        assert released.remaining_qty == 4

    def test_full_release_reserves_materials(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 3, 1)
        db.flush()
        release_manufacturing_order(db, mo.id, 3)

        abs_id = _abs_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv.reserved_quantity == 6.0  # 2 ABS × 3

    def test_release_already_released_raises(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 2, 1)
        db.flush()
        release_manufacturing_order(db, mo.id, 2)
        with pytest.raises(ProductionError, match="already released"):
            release_manufacturing_order(db, mo.id, 2)

    def test_release_insufficient_materials_raises(self, db):
        abs_id = _abs_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 0.0
        db.flush()

        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 1, 1)
        db.flush()
        with pytest.raises(ProductionError, match="Insufficient"):
            release_manufacturing_order(db, mo.id, 1)

    def test_release_exceeding_remaining_qty_raises(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 5, 1)
        db.flush()
        with pytest.raises(ProductionError, match="Invalid release quantity"):
            release_manufacturing_order(db, mo.id, 10)


class TestPartialRelease:
    def test_partial_release_creates_new_released_order(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 10, 1)
        db.flush()
        original_id = mo.id

        released = release_manufacturing_order(db, mo.id, 4)
        assert released.id != original_id
        assert released.status == "released"
        assert released.quantity == 4
        assert released.remaining_qty == 4

    def test_partial_release_reduces_original_order(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 10, 1)
        db.flush()
        original_id = mo.id

        release_manufacturing_order(db, mo.id, 4)

        original = db.query(ManufacturingOrder).filter_by(id=original_id).first()
        assert original.status == "pending"
        assert original.quantity == 6
        assert original.remaining_qty == 6

    def test_partial_release_reserves_correct_materials(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 10, 1)
        db.flush()

        release_manufacturing_order(db, mo.id, 3)

        abs_id = _abs_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        assert inv.reserved_quantity == 6.0  # 2 ABS × 3 units

    def test_double_reservation_blocked(self, db):
        """Releasing both parts must not over-reserve available stock."""
        abs_id = _abs_id(db)
        inv = db.query(Inventory).filter_by(material_id=abs_id).first()
        inv.quantity = 4.0  # only enough for 2 units (2 ABS each)
        db.flush()

        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 4, 1)
        db.flush()

        release_manufacturing_order(db, mo.id, 2)  # uses all 4 ABS
        remaining_mo = db.query(ManufacturingOrder).filter_by(id=mo.id).first()
        with pytest.raises(ProductionError, match="Insufficient"):
            release_manufacturing_order(db, remaining_mo.id, 2)


class TestCancelManufacturingOrder:
    def test_cancel_pending_order(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 3, 1)
        db.flush()
        cancelled = cancel_manufacturing_order(db, mo.id)
        assert cancelled.status == "cancelled"

    def test_cancel_released_order_unreserves_materials(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 2, 1)
        db.flush()
        release_manufacturing_order(db, mo.id, 2)

        abs_id = _abs_id(db)
        assert db.query(Inventory).filter_by(material_id=abs_id).first().reserved_quantity == 4.0

        cancel_manufacturing_order(db, mo.id)
        assert db.query(Inventory).filter_by(material_id=abs_id).first().reserved_quantity == 0.0

    def test_cancel_completed_order_raises(self, db):
        pid = _hobby_product_id(db)
        mo = create_manufacturing_order(db, pid, 1, 1)
        db.flush()
        mo.status = "completed"
        db.flush()
        with pytest.raises(ProductionError, match="Cannot cancel"):
            cancel_manufacturing_order(db, mo.id)

    def test_cancel_unknown_order_raises(self, db):
        with pytest.raises(ProductionError):
            cancel_manufacturing_order(db, 9999)
