"""Pydantic schemas for manufacturing orders."""

from pydantic import BaseModel


class BOMLineResponse(BaseModel):
    """Bill of Materials line item."""
    material_id: int
    material_name: str
    qty_per_unit: float
    total_required: float
    available: float
    shortage: float

    class Config:
        from_attributes = True


class ManufacturingOrderResponse(BaseModel):
    """Manufacturing order response."""
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    remaining_qty: int
    status: str
    bom: list[BOMLineResponse]

    class Config:
        from_attributes = True


class CreateManufacturingOrderRequest(BaseModel):
    """Request to create a manufacturing order."""
    product_id: int
    quantity: int


class ReleaseManufacturingOrderRequest(BaseModel):
    """Request to release a manufacturing order."""
    quantity: int
