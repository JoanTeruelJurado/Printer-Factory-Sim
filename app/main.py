from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import agent, dashboard, game, manufacturing, purchasing, sales
from app.db.database import init_db
from app.services.seed import seed_initial_data

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(
    title="3D Printer Factory Simulator",
    version="0.1.0",
    description="A turn-based 3D printer factory simulation with inventory, purchasing, and production management.",
)
app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(manufacturing.router, prefix="/api", tags=["manufacturing"])
app.include_router(purchasing.router, prefix="/api", tags=["purchasing"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(sales.router, prefix="/api", tags=["sales"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/{full_path:path}", response_class=FileResponse, include_in_schema=False)
def spa_fallback(full_path: str) -> Path:
    """Serve the React SPA for all non-API routes."""
    return FRONTEND_DIR / "index.html"


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_initial_data()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
