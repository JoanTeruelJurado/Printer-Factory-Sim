"""Tests for purchasing service with mocked supplier_client."""

import pytest
from app.db.models import GameState, Inventory, RawMaterial
from app.services.purchasing import PurchasingError, get_supplier_catalog, issue_purchase_order


def _abs_id(db):
    return db.query(RawMaterial).filter_by(name="ABS Filament").first().id


def _state(db) -> GameState:
    return db.query(GameState).filter_by(id=1).first()


class TestIssuePurchaseOrder:
    def test_creates_pending_po(self, db):
        mid = _abs_id(db)
        po = issue_purchase_order(db, 1, mid, 10, 1)
        assert po["status"] == "pending"
        assert po["quantity"] == 10
        assert po["supplier_id"] == 1
        assert po["material_id"] == mid

    def test_expected_delivery_day_is_lead_time_plus_current(self, db):
        mid = _abs_id(db)
        po = issue_purchase_order(db, 1, mid, 5, 3)
        # Mock supplier has lead_time_days=2, so 3+2=5
        assert po["expected_delivery_day"] == 5

    def test_deducts_cost_from_wallet(self, db):
        mid = _abs_id(db)
        state = _state(db)
        before = state.wallet_balance
        po = issue_purchase_order(db, 1, mid, 10, 1)
        assert state.wallet_balance == pytest.approx(before - po["total_cost"])

    def test_cost_equals_unit_price_times_quantity(self, db):
        mid = _abs_id(db)
        po = issue_purchase_order(db, 1, mid, 10, 1)
        # Mock ABS base price 28.0; qty=10 qualifies for 10% tier discount → 25.20/unit
        assert po["unit_cost"] == pytest.approx(28.0 * 0.90)
        assert po["total_cost"] == pytest.approx(28.0 * 0.90 * 10)

    def test_insufficient_funds_raises(self, db):
        _state(db).wallet_balance = 1.0
        db.flush()
        mid = _abs_id(db)
        with pytest.raises(PurchasingError, match="Insufficient funds"):
            issue_purchase_order(db, 1, mid, 100, 1)

    def test_warehouse_capacity_exceeded_raises(self, db):
        state = _state(db)
        # Current inventory is 3 materials × 150 = 450 units
        state.warehouse_capacity = 450
        db.flush()
        mid = _abs_id(db)
        with pytest.raises(PurchasingError, match="warehouse capacity"):
            issue_purchase_order(db, 1, mid, 1, 1)

    def test_supplier_api_error_raises_purchasing_error(self, db, monkeypatch):
        import app.services.supplier_client as sc

        def _fail(sid, mid, quantity=None):
            raise sc.SupplierAPIError("down")

        monkeypatch.setattr(sc, "get_pricing", _fail)
        mid = _abs_id(db)
        with pytest.raises(PurchasingError, match="Supplier API"):
            issue_purchase_order(db, 1, mid, 1, 1)

    def test_create_order_failure_raises_purchasing_error(self, db, monkeypatch):
        import app.services.supplier_client as sc

        def _fail(payload):
            raise sc.SupplierAPIError("down")

        monkeypatch.setattr(sc, "create_order", _fail)
        mid = _abs_id(db)
        with pytest.raises(PurchasingError, match="create order"):
            issue_purchase_order(db, 1, mid, 1, 1)

    def test_po_contains_material_name(self, db):
        mid = _abs_id(db)
        po = issue_purchase_order(db, 1, mid, 5, 1)
        assert po["material_name"] == "ABS Filament"

    def test_po_id_is_returned(self, db):
        mid = _abs_id(db)
        po = issue_purchase_order(db, 1, mid, 5, 1)
        assert "po_id" in po
        assert isinstance(po["po_id"], int)


class TestGetSupplierCatalog:
    def test_returns_supplier_info(self, db):
        catalog = get_supplier_catalog(db, 1)
        assert catalog["supplier_id"] == 1
        assert catalog["supplier_name"] == "TestSupplier"

    def test_catalog_contains_materials(self, db):
        catalog = get_supplier_catalog(db, 1)
        assert len(catalog["catalog"]) >= 1

    def test_supplier_api_error_raises_purchasing_error(self, db, monkeypatch):
        import app.services.supplier_client as sc

        def _fail(sid):
            raise sc.SupplierAPIError("down")

        monkeypatch.setattr(sc, "get_catalog", _fail)
        with pytest.raises(PurchasingError, match="Supplier API"):
            get_supplier_catalog(db, 1)
