from pydantic import BaseModel


class InventoryItemResponse(BaseModel):
    material_id: int
    material_name: str
    quantity: float
    reserved_quantity: float
    volume_per_unit: float
    total_volume: float

    class Config:
        from_attributes = True
