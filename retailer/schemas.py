"""
Pydantic v2 schemas for the Retailer App REST API.

Defines request/response models for catalog, customer orders,
purchase orders, stock, and game state endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Catalog ───────────────────────────────────────────────────────────────────

class CatalogResponse(BaseModel):
    id: int
    model_name: str
    description: Optional[str] = None
    retail_price: float
    wholesale_price: float

    model_config = {"from_attributes": True}


class CatalogListResponse(BaseModel):
    items: list[CatalogResponse]
    count: int


class PriceUpdateRequest(BaseModel):
    retail_price: float = Field(gt=0, description="New retail price")


class PriceUpdateResponse(BaseModel):
    model_name: str
    old_price: float
    new_price: float


# ── Customer Orders ──────────────────────────────────────────────────────────

class CustomerOrderRequest(BaseModel):
    customer_name: str = Field(default="auto", description="Customer name")
    model: str = Field(description="Printer model name from catalog")
    quantity: int = Field(ge=1, description="Number of units to order")


class CustomerOrderResponse(BaseModel):
    id: int
    customer_name: str
    model_name: str
    quantity: int
    status: str
    order_day: int
    fulfilled_day: Optional[int] = None

    model_config = {"from_attributes": True}


class CustomerOrderListResponse(BaseModel):
    orders: list[CustomerOrderResponse]
    count: int


# ── Purchase Orders ──────────────────────────────────────────────────────────

class PurchaseCreateRequest(BaseModel):
    model: str = Field(description="Printer model name from catalog")
    quantity: int = Field(ge=1, description="Number of units to order")


class PurchaseResponse(BaseModel):
    id: int
    model_name: str
    quantity: int
    status: str
    ordered_day: int
    expected_delivery_day: int
    delivered_day: Optional[int] = None
    unit_price: float
    total_price: float

    model_config = {"from_attributes": True}


class PurchaseListResponse(BaseModel):
    orders: list[PurchaseResponse]
    count: int


# ── Stock ────────────────────────────────────────────────────────────────────

class StockResponse(BaseModel):
    id: int
    model_name: str
    quantity_on_hand: int

    model_config = {"from_attributes": True}


class StockListResponse(BaseModel):
    items: list[StockResponse]
    count: int


# ── Day / Game State ────────────────────────────────────────────────────────

class DayResponse(BaseModel):
    current_day: int
    wallet_balance: float


class AdvanceDayResponse(BaseModel):
    success: bool
    new_day: int
    wallet_balance: float
    summary: dict
