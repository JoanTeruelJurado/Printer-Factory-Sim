from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Config, GameState, Inventory
from app.schemas import GameStateResponse, InventoryItemResponse
from app.services.seed import reset_game
from app.services.simulation import advance_day, SimulationError

router = APIRouter()


@router.get("/state", response_model=GameStateResponse)
def get_game_state(db: Session = Depends(get_db)) -> GameStateResponse:
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")

    warehouse_used = db.query(Inventory).with_entities(
        (Inventory.quantity + Inventory.reserved_quantity).label("used")
    ).all()
    total_used = sum(row.used for row in warehouse_used)

    warning_level = None
    capacity_threshold = db.query(Config).filter(Config.key == "capacity_warning_threshold").first()
    if capacity_threshold:
        try:
            threshold = float(capacity_threshold.value)
            if total_used >= state.warehouse_capacity * threshold:
                warning_level = "capacity"
        except ValueError:
            pass

    return GameStateResponse(
        current_day=state.current_day,
        wallet_balance=state.wallet_balance,
        warehouse_capacity=state.warehouse_capacity,
        warehouse_used=total_used,
        daily_production_capacity=state.daily_production_capacity,
        production_used_today=0,
        game_over=state.game_over,
        warning_level=warning_level,
    )


@router.get("/inventory", response_model=list[InventoryItemResponse])
def list_inventory(db: Session = Depends(get_db)) -> list[InventoryItemResponse]:
    inventory_rows = db.query(Inventory).join(Inventory.material).all()
    result: list[InventoryItemResponse] = []
    for item in inventory_rows:
        result.append(
            InventoryItemResponse(
                material_id=item.material_id,
                material_name=item.material.name,
                quantity=item.quantity,
                reserved_quantity=item.reserved_quantity,
                volume_per_unit=item.material.volume_per_unit,
                total_volume=item.quantity * item.material.volume_per_unit,
            )
        )
    return result


@router.post("/reset")
def reset_game_state(db: Session = Depends(get_db)) -> dict[str, str]:
    reset_game(db)
    return {"success": True, "message": "Game reset to initial state."}


@router.post("/advance-day")
def advance_day_endpoint(db: Session = Depends(get_db)) -> dict:
    """Advance simulation by one day."""
    try:
        state = db.query(GameState).filter(GameState.id == 1).first()
        if state is None:
            raise HTTPException(status_code=404, detail="Game state not found")
        
        if state.game_over:
            raise HTTPException(status_code=403, detail="Game is over")
        
        result = advance_day(db)
        return {
            "success": True,
            "data": result,
            "message": None,
        }
    except SimulationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")
