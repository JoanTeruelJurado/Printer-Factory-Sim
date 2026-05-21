"""Pydantic schemas for sales orders."""

from pydantic import BaseModel
from typing import Optional


class SalesOrderCreateRequest(BaseModel):
    """Request to create a sales order (inbound from retailer)."""
    retailer_name: str
    model: str
    quantity: int


class SalesOrderResponse(BaseModel):
    """Sales order response."""
    id: int
    retailer_name: str
    product_id: int
    product_name: str
    quantity: int
    status: str
    ordered_day: int
    released_day: Optional[int] = None
    completed_day: Optional[int] = None
    shipped_day: Optional[int] = None
    delivered_day: Optional[int] = None
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True
