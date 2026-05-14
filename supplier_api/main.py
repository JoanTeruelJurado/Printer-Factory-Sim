"""
Supplier API — standalone FastAPI application on port 8001.

Provides supplier catalog, pricing, and purchase order management.
The factory server (port 8000) calls this API via HTTP.
"""

import uvicorn
from fastapi import FastAPI

from supplier_api.database import init_db
from supplier_api.routes import router
from supplier_api.seed import seed_supplier_data

app = FastAPI(
    title="Supplier API",
    version="1.0.0",
    description="External supplier provider for the 3D Printer Factory Simulator.",
)

app.include_router(router)


@app.on_event("startup")
def startup_event() -> None:
    """Initialise DB schema and seed reference data on startup."""
    init_db()
    seed_supplier_data()


if __name__ == "__main__":
    uvicorn.run("supplier_api.main:app", host="0.0.0.0", port=8001, reload=True)
