from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import game, manufacturing, purchasing
from app.db.database import init_db
from app.services.seed import seed_initial_data

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="3D Printer Factory Simulator",
    version="0.1.0",
    description="A turn-based 3D printer factory simulation with inventory, purchasing, and production management.",
)
app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(manufacturing.router, prefix="/api", tags=["manufacturing"])
app.include_router(purchasing.router, prefix="/api", tags=["purchasing"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
def root() -> Path:
    return STATIC_DIR / "index.html"


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_initial_data()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
