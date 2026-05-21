"""
Retailer App — standalone FastAPI application on port 8003.

Provides a retail storefront for end customers purchasing 3D printers.
The retailer buys finished goods from the manufacturer (port 8002).
"""

import uvicorn
from fastapi import FastAPI

from retailer.database import init_db
from retailer.seed import seed_retailer_data

from retailer.api.catalog import router as catalog_router
from retailer.api.orders import router as orders_router
from retailer.api.purchases import router as purchases_router
from retailer.api.game import router as game_router

app = FastAPI(
    title="Retailer App",
    version="1.0.0",
    description="Retail storefront for the 3D Printer Factory Simulator.",
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(catalog_router, prefix="/api", tags=["catalog"])
app.include_router(orders_router, prefix="/api", tags=["orders"])
app.include_router(purchases_router, prefix="/api", tags=["purchases"])
app.include_router(game_router, prefix="/api", tags=["game"])


@app.on_event("startup")
def startup_event() -> None:
    """Initialise DB schema and seed reference data on startup."""
    init_db()
    seed_retailer_data()


if __name__ == "__main__":
    uvicorn.run("retailer.main:app", host="0.0.0.0", port=8003, reload=True)
