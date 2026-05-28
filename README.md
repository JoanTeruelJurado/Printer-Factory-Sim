# 3D Printer Factory Simulator

A discrete-event simulation of a full retail supply chain for 3D printers. Three autonomous microservices — Provider, Manufacturer, and Retailer — interact across simulated days. A Turn Engine orchestrates each day cycle, injects customer demand, and invokes AI agents at each node. You (or an AI agent) act as planner at any tier — managing inventory, purchasing, scheduling production, and fulfilling demand before the wallet runs dry.

## Tech Stack

- **Provider API**: Python 3.12 + FastAPI + SQLite (`supplier.db`, port 8001) — standalone supplier microservice
- **Manufacturer API**: Python 3.12 + FastAPI + SQLAlchemy + SQLite (`simulator.db`, port 8002) — factory production engine
- **Retailer API**: Python 3.12 + FastAPI + SQLite (`retailer.db`, port 8003) — retail storefront and order management
- **Frontend**: React 19 + Vite 5 + TailwindCSS v3, built and served by the Manufacturer API
- **Turn Engine**: Python orchestrator (`turn_engine.py`) that advances all three apps in lockstep

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

Then open **http://\<VM-IP\>:8002** in your browser (Manufacturer UI).

> On Multipass or a remote VM, get the IP with `hostname -I`.

To stop everything:

```bash
./stop.sh
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Provider API | http://localhost:8001 | Supplier microservice (materials catalog, pricing, purchase orders) |
| Provider docs | http://localhost:8001/docs | Provider API Swagger UI |
| Manufacturer API + UI | http://localhost:8002 | React frontend + Factory REST API |
| Manufacturer docs | http://localhost:8002/docs | Manufacturer API Swagger UI |
| Simulation Dashboard | http://localhost:8002 | Switch to the **Sim Dashboard** tab — 4 real-time SVG charts (inventory, prices, order fulfillment, wallet), scenario events timeline, and collapsible cross-service event logs |
| Retailer API | http://localhost:8003 | Retail storefront and order management |
| Retailer docs | http://localhost:8003/docs | Retailer API Swagger UI |

## CLIs

All three apps have a CLI for manual play or agent scripting.

### manufacturer-cli (Manufacturer API)

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

### provider-cli (Provider API)

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

### retailer-cli (Retailer API)

```bash
retailer-cli state                                        # Wallet, day, inventory snapshot
retailer-cli stock                                        # Finished goods on hand
retailer-cli orders list [--status STATUS]                # List sales orders
retailer-cli orders show ORDER_ID                         # Order detail
retailer-cli orders fulfill ORDER_ID                      # Fulfill a sales order
retailer-cli purchase create \
    --product NAME --qty N                                # Place a purchase order to manufacturer
retailer-cli purchase list [--status STATUS]              # List purchase orders from manufacturer
retailer-cli day advance                                  # Advance one retailer day
retailer-cli day current                                  # Current retailer day
retailer-cli export [FILE]                                # Export retailer state to JSON
retailer-cli import FILE                                  # Import retailer state from JSON
retailer-cli serve [--port 8003]                          # Start the REST API
```

## Project Layout

```
app/                        # Manufacturer API (port 8002)
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
    supplier_client.py      # HTTP client for the Provider API (reads manufacturer_config.json)
    seed.py                 # Initial data seeding + reset_game
  api/
    game.py                 # Game state, day advancement, export/import endpoints
    manufacturing.py        # Manufacturing order endpoints
    purchasing.py           # Suppliers + purchase order endpoints
    sales.py                # Sales order endpoints (B2B orders from Retailer)
    agent.py                # GET /api/agent/context — full state for AI agents
    dashboard.py            # /api/dashboard/* — combined 3-app state, autopilot,
                            #   aggregated event logs, and scenario event definitions

supplier_api/               # Provider API (port 8001) — standalone microservice
  main.py                   # FastAPI app entrypoint
  database.py               # SQLite engine (supplier.db)
  models.py                 # Supplier, SupplierProduct, PricingTier, Stock,
                            #   PurchaseOrder, SimState, SupplierEvent ORM models
  routes.py                 # All supplier endpoints (inter-service + CLI/agent)
  seed.py                   # Seeds 3 suppliers, 8 materials, 96 pricing tiers, stock

retailer/                   # Retailer API (port 8003) — standalone microservice
  main.py                   # FastAPI app entrypoint
  database.py               # SQLite engine (retailer.db)
  models.py                 # SalesOrder, RetailerInventory, RetailerPurchaseOrder,
                            #   RetailerState, RetailerEvent ORM models
  routes.py                 # Sales order, inventory, and day-advance endpoints
  seed.py                   # Seeds initial retailer state and product catalog

frontend/                   # React SPA (built output served by Manufacturer API)
  src/
    components/             # React components (GameHeader, tabs, modals)
      Tabs/
        SimDashboard.jsx    # Simulation Dashboard tab — 4 real-time SVG charts
                            #   (Inventory Over Time, Prices Over Time, Order Fulfillment,
                            #   Wallet Over Time), Scenario Events Timeline with colored
                            #   event bands, and collapsible Event Logs viewer aggregating
                            #   events from all 3 databases
    utils/                  # API helpers, constants
  dist/                     # Production build (generated by npm run build)

turn_engine/                # Turn Engine package (orchestrator)
  engine.py                 # Main orchestrator — advances all three apps in lockstep,
                            #   injects customer demand, invokes agent skills per role
  config.py                 # Loads config/sim.json and scenario files
  demand.py                 # Stochastic demand injection into Retailer

turn_engine.py              # Entry point: python turn_engine.py config/sim.json [scenario] [days]

config/
  sim.json                  # Simulation configuration (ports, wallet, capacity, agent models)

scenarios/
  smoke-test.json           # Short smoke-test scenario (3-day run)
  calm-market.json          # 25-day stable baseline scenario (control group)
  holiday-rush.json         # 25-day volatile scenario (Black Friday + chip shortage + Christmas)

skills/
  manufacturer-manager.md   # Skill prompt for the Manufacturer agent role
  provider-manager.md       # Skill prompt for the Provider agent role
  retail-manager.md         # Skill prompt for the Retailer agent role

logs/                       # Per-day, per-role log files (day-NNN-role.log)

tests/                      # pytest test suite (112 tests)
  conftest.py               # In-memory SQLite fixtures, supplier_client mock
  test_inventory.py
  test_production.py
  test_purchasing.py
  test_simulation.py
  test_api.py
  test_integration.py       # 14 cross-service integration tests

manufacturer_config.json    # Declares which provider URL the manufacturer calls
seed-provider.json          # Reproducible starting state for the Provider API
start.sh                    # Builds frontend, starts all three services
stop.sh                     # Stops all services
```

## Architecture

```
Turn Engine (turn_engine.py)
  │  reads config/sim.json + scenarios/*.json
  │  orchestrates one full day per iteration
  │  injects customer demand → Retailer
  │  invokes agent skills per role (skills/*.md)
  │  writes logs/day-NNN-role.log
  │
  ├────────────────────────────────────────────────────────────┐
  │                                                            │
  ▼                                                            ▼
Retailer API :8003  (FastAPI + SQLite: retailer.db)      Browser / AI Agent
  │  sales orders, inventory, day advance                      │
  │  GET /api/agent/context — retailer state snapshot          │
  │  GET /api/events — retailer event log                      │
  │                                                            │
  │  HTTP (purchase orders to manufacturer)                    │
  ▼                                                            ▼
Manufacturer API :8002  (FastAPI + SQLite: simulator.db) ◄─────┘
  │  serves React build at /
  │  exposes /api/* routes
  │
  ├── /api/game/*                   game state, advance day, export/import, reset
  ├── /api/manufacturing-orders/*   MO lifecycle
  ├── /api/suppliers, /api/purchase-orders
  ├── /api/agent/context            full state snapshot for AI agents
  ├── /api/dashboard/events         aggregated event logs from all 3 databases
  ├── /api/dashboard/scenario-events  scenario event definitions for timeline overlay
  │
  │           HTTP (supplier_client.py — reads manufacturer_config.json)
  ▼
Provider API :8001  (FastAPI + SQLite: supplier.db)
  │
  ├── GET  /suppliers, /suppliers/{id}/catalog, /suppliers/{id}/pricing/{mat_id}
  ├── POST /orders          create purchase order (inter-service)
  ├── GET  /orders/due      delivered orders waiting for factory acknowledgement
  ├── PUT  /orders/{id}/deliver
  ├── POST /prices/fluctuate
  ├── POST /api/day/advance  advance supplier day (called by manufacturer advance_day)
  ├── GET  /api/metrics       provider metrics history for dashboard charts
  ├── GET  /api/events        provider event log (filterable)
  └── GET/POST /api/*         CLI/agent endpoints (catalog, stock, orders, day, export/import)
```

## Week 7: Retail Supply Chain Orchestration

Week 7 extends the two-server system into a full three-tier supply chain and introduces a Turn Engine that orchestrates all apps in lockstep.

### Three-App Overview

| App | Role | Port | DB |
|-----|------|------|----|
| Provider | Raw material supplier | 8001 | supplier.db |
| Manufacturer | Factory — buys from Provider, sells to Retailer | 8002 | simulator.db |
| Retailer | Storefront — buys from Manufacturer, sells to end customers | 8003 | retailer.db |

Each app is independently runnable and exposes a `GET /api/agent/context` snapshot endpoint. Apps are decoupled: the Retailer only knows the Manufacturer's URL, and the Manufacturer only knows the Provider's URL.

### Turn Engine

The Turn Engine (`turn_engine.py`) is the single orchestrator responsible for progressing the simulation. It reads a config file and an optional scenario file, then for each day:

1. Injects synthetic customer demand orders into the Retailer
2. Calls `POST /api/game/advance-day` on the Retailer
3. Calls `POST /api/game/advance-day` on the Manufacturer (which also advances the Provider)
4. Invokes the configured agent skill for each role, passing the full context snapshot
5. Writes structured logs to `logs/day-NNN-role.log`

**Running the Turn Engine:**

```bash
# Run a 3-day smoke test
python turn_engine.py config/sim.json scenarios/smoke-test.json 3

# Run the calm-market scenario for 25 days
python turn_engine.py config/sim.json scenarios/calm-market.json 25

# Run the holiday-rush scenario for 25 days
python turn_engine.py config/sim.json scenarios/holiday-rush.json 25

# Run for N days with default config (no scenario file)
python turn_engine.py config/sim.json 10
```

**`config/sim.json`** declares service URLs, starting wallet, production capacity, and agent model settings.

**`scenarios/smoke-test.json`** defines a reproducible demand sequence for integration testing.

### Skill Files

Skill files in `skills/` are Markdown prompt documents that define how an AI agent should behave at each supply chain node. The Turn Engine injects the agent context snapshot and runs the skill via the configured model.

| File | Role |
|------|------|
| `skills/manufacturer-manager.md` | Guides the Manufacturer agent: when to buy materials, release MOs, and fulfill demand |
| `skills/provider-manager.md` | Guides the Provider agent: manage stock levels and adjust pricing tiers |
| `skills/retail-manager.md` | Guides the Retailer agent: fulfill customer orders, place purchase orders to Manufacturer, adjust retail pricing |

Each skill document describes the agent's goals, decision heuristics, available CLI commands, and output format.

### Logs and Analysis

Each Turn Engine run writes one log file per role per day:

```
logs/day-001-manufacturer.log
logs/day-001-retailer.log
logs/day-002-manufacturer.log
...
```

Log files contain the full agent context snapshot, the skill prompt, the agent's reasoning, and any CLI commands issued. Use these for debugging agent behaviour or auditing supply chain decisions.

### Post-Run Analysis

After a scenario run, `analysis.py` reads the per-app metrics tables from all three SQLite databases and generates charts for review:

```bash
# Generate charts for the holiday-rush scenario
python analysis.py --scenario holiday-rush \
    --scenario-file scenarios/holiday-rush.json \
    --output-dir charts

# Generate charts for the calm-market scenario
python analysis.py --scenario calm-market \
    --scenario-file scenarios/calm-market.json \
    --output-dir charts
```

Four chart types are produced:

1. **Inventory over time** — parts stock, finished-goods, and retailer stock levels across all three tiers
2. **Prices over time** — provider, manufacturer, and retailer price movements per day
3. **Order fulfillment bars** — orders placed, fulfilled, and backordered per day
4. **Scenario events overlay** — active events (demand/supply/lead-time modifiers) annotated on the timeline

The **Sim Dashboard** tab in the browser provides the same four charts as real-time SVG visualisations updated after each simulated day, plus a **Wallet Over Time** chart tracking cash balance. A **Scenario Events Timeline** renders colored event bands aligned to simulation days, and a collapsible **Event Logs** viewer aggregates events from all three databases (Manufacturer, Provider, Retailer) via `GET /api/dashboard/events`.

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

112 tests across 6 files. The Provider API is fully mocked in unit tests — no running services needed. The 14 integration tests in `test_integration.py` require all three services to be running.

## Environment Variables

```env
SUPPLIER_API_URL=http://localhost:8001   # Override the provider URL from manufacturer_config.json
```

## Troubleshooting

**Port already in use**
`start.sh` kills existing processes on ports 8001–8003 before starting. If a service still fails to bind, run `./stop.sh` then `./start.sh` again.

**Manufacturer cannot reach Provider**
Check `manufacturer_config.json` at the project root. The `provider_url` field must match the address where the Provider API is listening. The `SUPPLIER_API_URL` env var overrides this at runtime.

**Retailer cannot reach Manufacturer**
The Retailer reads its manufacturer URL from its own config (or env var). Verify the Manufacturer API is running on port 8002 before starting the Retailer.

**Turn Engine exits immediately**
Ensure all three services are running before invoking the Turn Engine. The engine performs a health check against each configured URL on startup and aborts if any service is unreachable.

**Tests fail with database errors**
Unit tests use an in-memory `StaticPool` SQLite database — they never touch `simulator.db` or `supplier.db`. If tests fail with schema errors, the ORM models may be out of sync with the test fixtures. Run `pytest tests/ -v --tb=short` for details.

**Frontend shows stale data after reset**
The React SPA does not auto-refresh on server-side reset. Reload the page manually (`Ctrl+R`) after calling `POST /api/game/reset`.
