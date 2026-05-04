# 3D Printer Factory Simulator

A discrete-event simulation of a 3D printer production factory. You play as production planner — managing inventory, purchasing materials, scheduling manufacturing orders, and fulfilling customer demand before your wallet runs dry.

## Tech Stack

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy + SQLite
- **Frontend**: React 19 + Vite 5 + TailwindCSS v3

## Getting Started

### 1. Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 3. Open in browser

| Service | URL |
|---------|-----|
| Game UI | http://localhost:5173 |
| API docs | http://localhost:8000/docs |

> If running on a remote VM (e.g. Multipass), replace `localhost` with the VM's IP address.

## Project Layout

```
app/
  main.py              # FastAPI app entrypoint
  db/
    database.py        # SQLite engine and session management
    models.py          # SQLAlchemy ORM models (14 tables)
  schemas/             # Pydantic request/response models
  services/
    simulation.py      # Core discrete-event engine (advance_day)
    production.py      # Manufacturing order logic
    purchasing.py      # Purchase order + supplier pricing
    inventory.py       # Material reservation and consumption
    demand.py          # Demand generation
    seed.py            # Initial data seeding
  api/
    game.py            # Game state + day advancement endpoints
    orders.py          # Manufacturing + purchase order endpoints
    products.py        # Product and supplier endpoints
frontend/              # React SPA (Vite dev server, proxies /api → :8000)
simulator.db           # SQLite database (auto-created on first run)
```

## Gameplay

- Each **day advance** generates new customer demand, processes production, delivers purchased materials, and deducts daily costs.
- You must **manually serve demand orders** before their due date to earn revenue.
- **Prices fluctuate ±10% daily** — buy materials strategically.
- The game ends if your **wallet goes negative**.

## Configuration

Set environment variables in a `.env` file at the project root:

```env
DATABASE_URL=sqlite:///./simulator.db
STARTING_WALLET=10000
DAILY_PRODUCTION_CAPACITY=10
```
