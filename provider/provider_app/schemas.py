from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PricingTierSchema(BaseModel):
    id: int
    min_qty: int
    max_qty: Optional[int]
    price_per_unit: float

    model_config = {"from_attributes": True}


class ProductSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    lead_time_days: int
    active: bool
    pricing_tiers: list[PricingTierSchema]

    model_config = {"from_attributes": True}


class StockItemSchema(BaseModel):
    product_id: int
    product_name: str
    quantity: int


class OrderSchema(BaseModel):
    id: int
    buyer_name: str
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    placed_day: int
    expected_delivery_day: int
    confirmed_day: Optional[int]
    shipped_day: Optional[int]
    delivered_day: Optional[int]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateOrderRequest(BaseModel):
    buyer: str
    product_id: int
    quantity: int


class SetPriceRequest(BaseModel):
    price: float


class RestockRequest(BaseModel):
    quantity: int
