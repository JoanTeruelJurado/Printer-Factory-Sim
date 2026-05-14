"""Purchase orders and suppliers API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import GameState
from app.schemas.purchase import (
    SupplierResponse,
    SupplierCatalogResponse,
    MaterialPricingResponse,
    PurchaseOrderResponse,
    CreatePurchaseOrderRequest,
)
from app.services.purchasing import (
    list_suppliers,
    list_purchase_orders,
    get_supplier_catalog,
    get_material_pricing,
    issue_purchase_order,
    PurchasingError,
)

router = APIRouter()


@router.get("/suppliers", response_model=list[SupplierResponse])
def get_suppliers(db: Session = Depends(get_db)) -> list[SupplierResponse]:
    """List all suppliers."""
    try:
        suppliers = list_suppliers(db)
    except PurchasingError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return [SupplierResponse(**s) for s in suppliers]


@router.get("/suppliers/{supplier_id}/catalog", response_model=SupplierCatalogResponse)
def get_catalog(supplier_id: int, db: Session = Depends(get_db)) -> SupplierCatalogResponse:
    """Get supplier's product catalog with current pricing."""
    try:
        catalog = get_supplier_catalog(db, supplier_id)
        return SupplierCatalogResponse(**catalog)
    except PurchasingError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "/suppliers/{supplier_id}/pricing/{material_id}",
    response_model=MaterialPricingResponse,
)
def get_pricing(
    supplier_id: int,
    material_id: int,
    db: Session = Depends(get_db),
) -> MaterialPricingResponse:
    """Get pricing for a specific material from a supplier."""
    try:
        pricing = get_material_pricing(db, supplier_id, material_id)
        return MaterialPricingResponse(**pricing)
    except PurchasingError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
def list_orders(db: Session = Depends(get_db)) -> list[PurchaseOrderResponse]:
    """List all purchase orders."""
    try:
        orders = list_purchase_orders(db)
    except PurchasingError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return [PurchaseOrderResponse(**o) for o in orders]


@router.post("/purchase-orders", response_model=PurchaseOrderResponse)
def create_order(
    req: CreatePurchaseOrderRequest,
    db: Session = Depends(get_db),
) -> PurchaseOrderResponse:
    """Issue a new purchase order."""
    try:
        game_state = db.query(GameState).filter_by(id=1).first()
        if not game_state:
            raise HTTPException(status_code=404, detail="Game state not found")

        if game_state.game_over:
            raise HTTPException(status_code=403, detail="Game is over")

        order_data = issue_purchase_order(
            db,
            req.supplier_id,
            req.material_id,
            req.quantity,
            game_state.current_day,
        )
        db.commit()

        return PurchaseOrderResponse(**order_data)
    except PurchasingError as e:
        raise HTTPException(status_code=422, detail=str(e))
