from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    product_type = Column(Enum("raw", "finished", name="product_type_enum"), nullable=False)
    status = Column(Enum("active", "discontinued", name="product_status_enum"), nullable=False, default="active")
    sell_price = Column(Float, nullable=True)
    assembly_time_hours = Column(Float, nullable=False, default=0.0)

    bom_lines = relationship("BOM", back_populates="product")


class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    base_price = Column(Float, nullable=False)
    volume_per_unit = Column(Float, nullable=False, default=1.0)

    inventory = relationship("Inventory", back_populates="material", uselist=False)
    bom_lines = relationship("BOM", back_populates="material")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    demand_orders = relationship("DemandOrder", back_populates="client")


class BOM(Base):
    __tablename__ = "bom"
    __table_args__ = (CheckConstraint("qty_needed > 0", name="ck_bom_qty_positive"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    qty_needed = Column(Float, nullable=False)

    product = relationship("Product", back_populates="bom_lines")
    material = relationship("RawMaterial", back_populates="bom_lines")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
    )

    material_id = Column(Integer, ForeignKey("raw_materials.id"), primary_key=True)
    quantity = Column(Float, nullable=False, default=0.0)
    reserved_quantity = Column(Float, nullable=False, default=0.0)

    material = relationship("RawMaterial", back_populates="inventory")


class ManufacturingOrder(Base):
    __tablename__ = "manufacturing_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_manufacturing_quantity_positive"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    created_day = Column(Integer, nullable=False)
    release_day = Column(Integer, nullable=True)
    completed_day = Column(Integer, nullable=True)
    status = Column(
        Enum("pending", "released", "completed", "cancelled", name="manufacturing_status_enum"),
        nullable=False,
        default="pending",
    )
    remaining_qty = Column(Integer, nullable=False, default=0)

    product = relationship("Product")


class DemandOrder(Base):
    __tablename__ = "demand_orders"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_demand_quantity_positive"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    request_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)
    status = Column(
        Enum("open", "fulfilled", "partial", "lost", name="demand_status_enum"),
        nullable=False,
        default="open",
    )
    fulfilled_qty = Column(Integer, nullable=False, default=0)
    penalty_amount = Column(Float, nullable=False, default=0.0)

    client = relationship("Client", back_populates="demand_orders")
    product = relationship("Product")


class DailyCosts(Base):
    __tablename__ = "daily_costs"

    id = Column(Integer, primary_key=True)
    fixed_cost = Column(Float, nullable=False, default=0.0)
    variable_cost_per_unit = Column(Float, nullable=False, default=0.0)
    energy_cost_per_hour = Column(Float, nullable=False, default=0.0)
    maintenance_percentage = Column(Float, nullable=False, default=0.0)


class GameState(Base):
    __tablename__ = "game_state"

    id = Column(Integer, primary_key=True)
    current_day = Column(Integer, nullable=False, default=1)
    wallet_balance = Column(Float, nullable=False, default=10000.0)
    warehouse_capacity = Column(Integer, nullable=False, default=10000)
    daily_production_capacity = Column(Integer, nullable=False, default=10)
    days_with_negative_balance = Column(Integer, nullable=False, default=0)
    game_over = Column(Boolean, nullable=False, default=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    sim_day = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    details = Column(Text, nullable=False)
    category = Column(
        Enum("production", "purchase", "demand", "inventory", "financial", "system", "alert", name="event_category_enum"),
        nullable=False,
        default="general",
    )


class LocalPurchaseOrder(Base):
    """Local copy of purchase orders placed with the Supplier API.

    Kept in the factory DB so the manufacturer knows what is on the way
    even if the Supplier API is temporarily unavailable.
    Status is a simplified view: pending → delivered.
    """

    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_po_id = Column(Integer, nullable=False, unique=True)
    supplier_id = Column(Integer, nullable=False)
    supplier_name = Column(String, nullable=True)
    material_id = Column(Integer, nullable=False)
    material_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    issue_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending")
    actual_delivery_day = Column(Integer, nullable=True)


class Config(Base):
    __tablename__ = "config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
