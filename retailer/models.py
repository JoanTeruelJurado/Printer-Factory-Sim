"""
SQLAlchemy ORM models for the Retailer App.

Stores the retailer's product catalog, customer orders, purchase orders
placed with the manufacturer, stock levels, game state, and events.
Fully independent — no imports from app/ or supplier_api/.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
)

from retailer.database import Base


class Catalog(Base):
    """Retailer's product catalog — finished printers available for sale."""

    __tablename__ = "catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    retail_price = Column(Float, nullable=False)
    wholesale_price = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerOrder(Base):
    """Orders placed by end customers buying printers from the retailer."""

    __tablename__ = "customer_orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_customer_order_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String, nullable=False, default="auto")
    model_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(
        Enum(
            "pending", "fulfilled", "backordered", "cancelled",
            name="customer_order_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    order_day = Column(Integer, nullable=False)
    fulfilled_day = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RetailerPurchaseOrder(Base):
    """Purchase orders placed by the retailer with the manufacturer."""

    __tablename__ = "retailer_purchase_orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_retailer_po_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(
        Enum(
            "pending", "shipped", "delivered",
            name="retailer_po_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    ordered_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    delivered_day = Column(Integer, nullable=True)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RetailerStock(Base):
    """Current inventory held by the retailer for each printer model."""

    __tablename__ = "retailer_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, unique=True, nullable=False)
    quantity_on_hand = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class RetailerGameState(Base):
    """Singleton game state for the retailer (id=1)."""

    __tablename__ = "retailer_game_state"

    id = Column(Integer, primary_key=True)
    current_day = Column(Integer, nullable=False, default=1)
    wallet_balance = Column(Float, nullable=False, default=50000.0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class RetailerEvent(Base):
    """Append-only audit log of all meaningful state changes in the Retailer App."""

    __tablename__ = "retailer_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    detail = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RetailerMetrics(Base):
    """Daily metrics snapshot for post-run analysis."""

    __tablename__ = "retailer_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    # Stock per model stored as JSON: {"P3D-Classic": 5, "P3D-Pro": 3}
    printer_stock_json = Column(String, nullable=False, default="{}")
    # Retail price per model stored as JSON
    retail_price_json = Column(String, nullable=False, default="{}")
    # Order counts for this day
    customer_orders_placed = Column(Integer, nullable=False, default=0)
    customer_orders_fulfilled = Column(Integer, nullable=False, default=0)
    customer_orders_backordered = Column(Integer, nullable=False, default=0)
    wallet_balance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
