from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from provider_app.db import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    lead_time_days = Column(Integer, nullable=False, default=2)
    active = Column(Boolean, nullable=False, default=True)

    pricing_tiers = relationship(
        "PricingTier",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PricingTier.min_qty",
    )
    stock = relationship("Stock", back_populates="product", uselist=False, cascade="all, delete-orphan")
    orders = relationship("ProviderOrder", back_populates="product")


class PricingTier(Base):
    __tablename__ = "pricing_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    min_qty = Column(Integer, nullable=False)
    max_qty = Column(Integer, nullable=True)  # None = unlimited
    price_per_unit = Column(Float, nullable=False)

    product = relationship("Product", back_populates="pricing_tiers")


class Stock(Base):
    __tablename__ = "stock"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="stock")


class ProviderOrder(Base):
    """Purchase order placed by a buyer (e.g. manufacturer) with this provider.

    State machine: pending → confirmed → shipped → delivered
                   pending/confirmed → cancelled
    """

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_name = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    placed_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    confirmed_day = Column(Integer, nullable=True)
    shipped_day = Column(Integer, nullable=True)
    delivered_day = Column(Integer, nullable=True)
    # pending | confirmed | shipped | delivered | cancelled
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    product = relationship("Product", back_populates="orders")


class SimulationDay(Base):
    """Singleton row (id=1) tracking the provider's current simulation day."""

    __tablename__ = "simulation_day"

    id = Column(Integer, primary_key=True)
    current_day = Column(Integer, nullable=False, default=1)


class Event(Base):
    """Append-only audit log for every meaningful state change."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    day = Column(Integer, nullable=False)
    details = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
