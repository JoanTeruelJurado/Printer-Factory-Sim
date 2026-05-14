"""
SQLAlchemy ORM models for the Supplier API.

Stores suppliers, supplier-material catalog, and purchase orders.
Material names are stored directly (no FK to factory DB).
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
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


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_purchase_quantity_positive"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    material_id = Column(Integer, nullable=False)
    material_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    packaging_type = Column(String, nullable=False, default="unit")
    issue_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    actual_delivery_day = Column(Integer, nullable=True)
    status = Column(
        Enum("pending", "delivered", "delayed", "cancelled", name="purchase_status_enum"),
        nullable=False,
        default="pending",
    )
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)

    supplier = relationship("Supplier", back_populates="purchase_orders")
