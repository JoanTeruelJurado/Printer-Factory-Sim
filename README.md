# 3D Printer Factory Simulator

A discrete-event simulation of a 3D printer production factory connected to a live supplier microservice. You (or an AI agent) act as production planner — managing inventory, purchasing materials from suppliers, scheduling manufacturing orders, and fulfilling customer demand before your wallet runs dry.

## Tech Stack

- **Factory API**: Python 3.12 + FastAPI + SQLAlchemy + SQLite (`simulator.db`, port 8000)
- **Supplier API**: Python 3.12 + FastAPI + SQLite (`supplier.db`, port 8001) — standalone microservice the factory calls via HTTP
- **Frontend**: React 19 + Vite 5 + TailwindCSS v3, built and served by the Factory API

## Quick Start

```bash
# Install Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend deps (one-time)
cd frontend && npm install && cd ..

# Launch everything
./start.sh
```

Then open **http://\<VM-IP\>:8000** in your browser.

> On Multipass or a remote VM, get the IP with `hostname -I`.

To stop everything:

```bash
./stop.sh
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Game UI + API | http://localhost:8000 | React frontend + Factory REST API |
| API docs | http://localhost:8000/docs | Interactive Swagger UI |
| Supplier API | http://localhost:8001 | Supplier microservice |
| Supplier docs | http://localhost:8001/docs | Supplier API Swagger UI |

## CLIs

Both apps have a CLI for manual play or agent scripting.

### manufacturer-cli (Factory API)

```bash
manufacturer-cli suppliers list                           # List all suppliers
manufacturer-cli suppliers catalog --supplier NAME        # Catalog with pricing tiers
manufacturer-cli stock                                    # Raw material inventory
manufacturer-cli purchase list [--status STATUS]          # List purchase orders
manufacturer-cli purchase create \
    --supplier NAME --material NAME --qty N               # Place a purchase order
manufacturer-cli day current                              # Current simulation day
manufacturer-cli day advance                              # Advance one day
manufacturer-cli export [FILE]                            # Export factory state to JSON
manufacturer-cli import FILE                              # Import factory state from JSON
```

### provider-cli (Supplier API)

```bash
provider-cli catalog                                      # Products with pricing tiers
provider-cli stock                                        # Current inventory
provider-cli orders list [--status STATUS]                # List orders
provider-cli orders show ORDER_ID                         # Order detail
provider-cli price set TIER_ID PRICE                      # Update a pricing tier
provider-cli restock SP_ID QUANTITY                       # Add to supplier stock
provider-cli day advance                                  # Process one supplier day
provider-cli day current                                  # Current supplier day
provider-cli export [FILE]                                # Export supplier state to JSON
provider-cli import FILE                                  # Import supplier state from JSON
provider-cli serve [--port 8001]                          # Start the REST API
```

## Project Layout

```
app/                        # Factory API (port 8000)
  main.py                   # FastAPI app — serves React build + /api/* routes
  db/
    database.py             # SQLite engine and session (simulator.db)
    models.py               # ORM models: GameState, Inventory, ManufacturingOrder,
                            #   DemandOrder, LocalPurchaseOrder, Event, …
  schemas/                  # Pydantic request/response models
  services/
    simulation.py           # Core discrete-event engine (advance_day)
    production.py           # Manufacturing order logic
    purchasing.py           # Purchase orders + supplier pricing
    inventory.py            # Material reservation and consumption
    supplier_client.py      # HTTP client for the Supplier API (reads manufacturer_config.json)
    seed.py                 # Initial data seeding + reset_game
  api/
    game.py                 # Game state, day advancement, export/import endpoints
    manufacturing.py        # Manufacturing order endpoints
    purchasing.py           # Suppliers + purchase order endpoints
    agent.py                # GET /api/agent/context — full state for AI agents

supplier_api/               # Supplier API (port 8001) — standalone microservice
  main.py                   # FastAPI app entrypoint
  database.py               # SQLite engine (supplier.db)
  models.py                 # Supplier, SupplierProduct, PricingTier, Stock,
                            #   PurchaseOrder, SimState, SupplierEvent ORM models
  routes.py                 # All supplier endpoints (inter-service + CLI/agent)
  seed.py                   # Seeds 3 suppliers, 8 materials, 96 pricing tiers, stock

frontend/                   # React SPA (built output served by FastAPI)
  src/
    components/             # React components (GameHeader, tabs, modals)
    utils/                  # API helpers, constants
  dist/                     # Production build (generated by npm run build)

tests/                      # pytest test suite (98 tests)
  conftest.py               # In-memory SQLite fixtures, supplier_client mock
  test_inventory.py
  test_production.py
  test_purchasing.py
  test_simulation.py
  test_api.py

manufacturer_config.json    # Declares which provider URL the manufacturer calls
seed-provider.json          # Reproducible starting state for the Supplier API
start.sh                    # Builds frontend, starts Supplier API + Factory API
stop.sh                     # Stops all services
```

## Architecture

```
Browser / AI Agent
  │
  ▼
Factory API :8000  (FastAPI + SQLite: simulator.db)
  │  serves React build at /
  │  exposes /api/* routes
  │
  ├── /api/game/*                   game state, advance day, export/import, reset
  ├── /api/manufacturing-orders/*   MO lifecycle
  ├── /api/suppliers, /api/purchase-orders
  ├── /api/agent/context            full state snapshot for AI agents
  │
  │           HTTP (supplier_client.py — reads manufacturer_config.json)
  ▼
Supplier API :8001  (FastAPI + SQLite: supplier.db)
  │
  ├── GET  /suppliers, /suppliers/{id}/catalog, /suppliers/{id}/pricing/{mat_id}
  ├── POST /orders          create purchase order (inter-service)
  ├── GET  /orders/due      delivered orders waiting for factory acknowledgement
  ├── PUT  /orders/{id}/deliver
  ├── POST /prices/fluctuate
  ├── POST /api/day/advance  advance supplier day (called by factory advance_day)
  └── GET/POST /api/*        CLI/agent endpoints (catalog, stock, orders, day, export/import)
```

## Gameplay Loop

Each **Advance Day** triggers in sequence:

1. Supplier prices fluctuate ±10%
2. Supplier day advances (pending orders ship; due orders deliver — subject to reliability)
3. New customer demand orders generated (1–2 per day, due in 3–7 days)
4. Delivered purchase orders received into factory inventory
5. Released manufacturing orders produced up to daily capacity
6. Expired unfulfilled demand orders marked lost (€50/unit penalty)
7. Daily costs deducted (€500 fixed + variable production costs)
8. Game-over check (wallet negative 3 consecutive days → game over)

**You must manually serve demand orders** before their due date to earn revenue.

## Suppliers

Three suppliers, each with different lead times and reliability:

| Supplier | Lead time | Reliability | Pricing |
|----------|-----------|-------------|---------|
| Industrial Materials Co. | 3 days | 95% | Premium |
| QuickShip Components | 1 day | 85% | Cheapest |
| Global Sourcing Ltd | 7 days | 98% | Mid-range |

**Pricing tiers** (discount by quantity):

| Quantity | Discount |
|----------|----------|
| 1–9 units | 0% (base price) |
| 10–49 units | −10% |
| 50–99 units | −18% |
| 100+ units | −25% |

**Reliability** is a per-delivery probability. On failure the order is delayed 1–3 extra days and retried.

## Key Business Rules

| Rule | Value |
|------|-------|
| Starting wallet | €10,000 |
| Daily fixed cost | €500 |
| Variable cost per unit | €50 |
| Late/lost demand penalty | €50 per unfulfilled unit |
| Game over after | 3 consecutive days with negative wallet |
| Warehouse capacity | 10,000 units |
| Default production capacity | 10 units/day |
| Price fluctuation | ±10% daily |
| Supplier stock replenishment | 15 units/day (max 500) |

## Agent Context Endpoint

`GET /api/agent/context` returns a single JSON object with the complete game state for AI agent consumption: wallet, inventory with available quantities, products with BOM and max producible units, open demand orders with days remaining and potential revenue, active manufacturing orders, pending purchase orders, and the full supplier catalog with per-tier effective prices and affordability constraints.

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

98 tests across 5 files. The supplier API is fully mocked — no running services needed.

## Environment Variables

```env
SUPPLIER_API_URL=http://localhost:8001   # Override the URL from manufacturer_config.json
```
