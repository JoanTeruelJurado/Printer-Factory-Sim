"""
SQLAlchemy ORM models for the Supplier API.

Stores suppliers, supplier-material catalog, purchase orders,
pricing tiers, stock levels, simulated time, and events.
Material names are stored directly (no FK to factory DB).
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from supplier_api.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    lead_time_days = Column(Integer, nullable=False, default=0)
    reliability = Column(Float, nullable=False, default=1.0)

    supplier_products = relationship("SupplierProduct", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class SupplierProduct(Base):
    __tablename__ = "supplier_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    # material_id is the factory's raw_materials.id (referenced by value, not FK)
    material_id = Column(Integer, nullable=False)
    material_name = Column(String, nullable=False)
    base_unit_cost = Column(Float, nullable=False)
    daily_price_factor = Column(Float, nullable=False, default=1.0)

    supplier = relationship("Supplier", back_populates="supplier_products")
    pricing_tiers = relationship(
        "PricingTier", back_populates="supplier_product", cascade="all, delete-orphan"
    )
    stock = relationship(
        "Stock", back_populates="supplier_product", uselist=False, cascade="all, delete-orphan"
    )


class PricingTier(Base):
    """Quantity-based pricing tiers for a supplier-product combination."""

    __tablename__ = "pricing_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_product_id = Column(Integer, ForeignKey("supplier_products.id"), nullable=False)
    min_quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    supplier_product = relationship("SupplierProduct", back_populates="pricing_tiers")


class Stock(Base):
    """Current inventory held by each supplier for each product."""

    __tablename__ = "stock"

    supplier_product_id = Column(
        Integer, ForeignKey("supplier_products.id"), primary_key=True
    )
    quantity = Column(Integer, nullable=False, default=0)

    supplier_product = relationship("SupplierProduct", back_populates="stock")


class SimState(Base):
    """Key-value store for supplier simulation state (e.g. current_day)."""

    __tablename__ = "sim_state"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class SupplierEvent(Base):
    """Audit log of all meaningful state changes in the Supplier API."""

    __tablename__ = "supplier_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    detail = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_purchase_quantity_positive"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    buyer = Column(String, nullable=True, default="factory")
    material_id = Column(Integer, nullable=False)
    material_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    packaging_type = Column(String, nullable=False, default="unit")
    issue_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    shipped_day = Column(Integer, nullable=True)
    actual_delivery_day = Column(Integer, nullable=True)
    status = Column(
        Enum(
            "pending", "shipped", "delivered", "received", "delayed", "cancelled",
            name="purchase_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)

    supplier = relationship("Supplier", back_populates="purchase_orders")


class ProviderMetrics(Base):
    """Daily metrics snapshot for post-run analysis."""

    __tablename__ = "provider_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    # Stock per product stored as JSON: {"pcb": 450, "extruder": 380}
    stock_json = Column(String, nullable=False, default="{}")
    # Price per product (top tier) stored as JSON
    price_json = Column(String, nullable=False, default="{}")
    # Order counts for this day
    orders_pending = Column(Integer, nullable=False, default=0)
    orders_shipped = Column(Integer, nullable=False, default=0)
    orders_delivered = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
