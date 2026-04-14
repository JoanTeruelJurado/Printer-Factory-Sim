from pydantic import BaseModel


class GameStateResponse(BaseModel):
    current_day: int
    wallet_balance: float
    warehouse_capacity: int
    warehouse_used: float
    daily_production_capacity: int
    production_used_today: int
    game_over: bool
    warning_level: str | None = None

    class Config:
        from_attributes = True
