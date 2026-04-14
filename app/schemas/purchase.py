"""Pydantic schemas for purchase orders."""

from pydantic import BaseModel


class SupplierResponse(BaseModel):
    """Supplier info."""
    supplier_id: int
    supplier_name: str
    lead_time_days: int
    reliability: float

    class Config:
        from_attributes = True


class MaterialPricingResponse(BaseModel):
    """Material pricing from a specific supplier."""
    supplier_id: int
    supplier_name: str
    material_id: int
    material_name: str
    base_unit_cost: float
    daily_price_factor: float
    current_price_per_unit: float
    lead_time_days: int

    class Config:
        from_attributes = True


class CatalogItemResponse(BaseModel):
    """Supplier catalog item."""
    material_id: int
    material_name: str
    base_unit_cost: float
    daily_price_factor: float
    current_price: float

    class Config:
        from_attributes = True


class SupplierCatalogResponse(BaseModel):
    """Supplier catalog."""
    supplier_id: int
    supplier_name: str
    lead_time_days: int
    reliability: float
    catalog: list[CatalogItemResponse]

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    """Purchase order details."""
    po_id: int
    supplier_id: int
    supplier_name: str
    material_id: int
    material_name: str
    quantity: int
    issue_day: int
    expected_delivery_day: int
    actual_delivery_day: int | None
    status: str
    unit_cost: float
    total_cost: float

    class Config:
        from_attributes = True


class CreatePurchaseOrderRequest(BaseModel):
    """Request to create a purchase order."""
    supplier_id: int
    material_id: int
    quantity: int
