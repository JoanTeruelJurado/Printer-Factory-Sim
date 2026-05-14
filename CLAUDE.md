# Project: 3D Printer Production Simulator

## What This Is
A discrete-event simulation system that models the full production cycle of a factory manufacturing 3D printers. The user acts as production planner, making decisions about what to manufacture and what materials to purchase while managing inventory, costs, and production capacity. The game ends if the wallet goes negative for 3 consecutive days.

## Tech Stack
- **Python 3.12** — Factory API + Supplier API
- **FastAPI + Pydantic v2** — REST API with automatic OpenAPI documentation
- **React 19 + Vite 5 + TailwindCSS v3** — Frontend SPA, built and served by the Factory API
- **SQLite** — Two separate databases: `simulator.db` (factory) and `supplier.db` (supplier)
- **SQLAlchemy ORM** — Database access layer
- **httpx** — Synchronous HTTP client used by `supplier_client.py`
- **pytest + httpx** — Test suite (98 tests)
- **Custom discrete-event loop** — Turn-based day progression

## Architecture

### Two-Server Design

```
Browser
  │
  ▼
Factory API :8000  (FastAPI + SQLite: simulator.db)
  │  serves React build at /
  │  exposes /api/* routes
  │
  ├── /api/game/*                   game state, advance day, export/import
  ├── /api/manufacturing-orders/*   MO lifecycle
  └── /api/suppliers, /api/purchase-orders
           │
           ▼  HTTP via supplier_client.py
      Supplier API :8001  (FastAPI + SQLite: supplier.db)
           │
           ├── GET  /suppliers
           ├── GET  /suppliers/{id}/catalog
           ├── GET  /suppliers/{id}/pricing/{material_id}
           ├── POST /orders
           ├── GET  /orders
           ├── GET  /orders/due?day=N
           ├── PUT  /orders/{id}/deliver
           ├── POST /prices/fluctuate
           └── DELETE /orders
```

The Factory API never touches supplier.db directly. All supplier/pricing/PO data goes through the Supplier API via `app/services/supplier_client.py`.

### Key Architecture Decisions

1. **Two-Server Split**: Supplier logic (catalog, pricing, purchase orders) lives in a standalone FastAPI app (`supplier_api/`) with its own SQLite DB. The factory communicates via HTTP through `supplier_client.py`. This keeps the factory decoupled from supplier internals.

2. **supplier_client.py**: Thin HTTP wrapper around all Supplier API calls. Raises `SupplierAPIError` on connection failure. Both `process_purchase_deliveries` and `apply_daily_price_fluctuation` degrade gracefully if the Supplier API is down.

3. **React SPA served by FastAPI**: The React build (`frontend/dist/`) is served as static files by the Factory API. No separate dev server in production. `spa_fallback` route returns `index.html` for all non-API paths.

4. **Custom Simulation Engine**: Turn-based day progression with explicit boundaries. Each `advance_day()` call runs: price fluctuation → demand generation → purchase deliveries → production → expire demands + apply penalties → deduct costs → game-over check.

5. **Service Layer Pattern**: Routes handle HTTP; services handle business logic. Testable without HTTP overhead.

6. **Singleton Game State**: Only one game instance at a time. `game_state` table has `id = 1`.

7. **Event-Sourced Logging**: All state changes logged to `events` table with JSON `details`. 14+ event types.

8. **Manual Demand Fulfillment**: Revenue is NOT collected automatically. The player must serve each demand order via the UI. On-time → full revenue. Late → no revenue. Expired → €50/unit penalty deducted from wallet.

9. **Finished Goods Accounting**: Available stock = sum of completed MO quantities − already-fulfilled demand quantities. Computed on-the-fly; no separate finished-goods table.

10. **Material Reservation Model**: Materials are reserved when an MO is released (not consumed). Consumed when production completes. Unreserved on cancel. Prevents double-allocation.

11. **Daily Price Fluctuation**: Supplier API recalculates `daily_price_factor` (±10%) on each `POST /prices/fluctuate` call, triggered at the start of every `advance_day`.

12. **Partial Order Handling**: Release N < MO.quantity → splits into a new released MO (N units) + the original shrinks to (quantity − N). `remaining_qty` tracks production progress.

## File Structure

```
app/                          # Factory API
  main.py                     # FastAPI app; serves React build + /api/* routes
  db/
    database.py               # Engine, SessionLocal, Base, get_db, init_db
    models.py                 # ORM: GameState, DailyCosts, Config, Client,
                              #   Product, RawMaterial, BOM, Inventory,
                              #   ManufacturingOrder, DemandOrder, Event
  schemas/
    __init__.py
    inventory.py              # InventoryItemResponse
    manufacturing.py          # ManufacturingOrderResponse, BOMLineResponse, etc.
    order.py                  # GameStateResponse
  services/
    simulation.py             # advance_day(), generate_demand_orders(),
                              #   process_production(), mark_expired_demands(),
                              #   calculate_daily_costs(), check_game_over()
    production.py             # create_mo(), release_mo(), cancel_mo()
    purchasing.py             # issue_purchase_order(), list_suppliers(),
                              #   get_supplier_catalog(), list_purchase_orders()
    inventory.py              # reserve_materials(), consume_materials(),
                              #   unreserve_materials(), check_material_availability()
    supplier_client.py        # HTTP client for Supplier API (httpx, sync)
    seed.py                   # seed_initial_data(), reset_game()
  api/
    game.py                   # /api/game/* endpoints
    manufacturing.py          # /api/manufacturing-orders/* endpoints
    purchasing.py             # /api/suppliers/*, /api/purchase-orders endpoints

supplier_api/                 # Supplier API (standalone, port 8001)
  main.py                     # FastAPI app; calls init_db() + seed() on startup
  database.py                 # Engine for supplier.db
  models.py                   # Supplier, SupplierProduct, PurchaseOrder
  routes.py                   # All 9 supplier endpoints
  seed.py                     # 3 suppliers, 8 materials, 24 SupplierProduct links

frontend/
  src/
    components/               # React components
    utils/                    # api.js helpers, constants.js
  dist/                       # Production build (served by FastAPI)

tests/
  conftest.py                 # StaticPool in-memory SQLite; supplier_client autouse mock;
                              #   engine/db/client fixtures
  test_inventory.py           # 12 tests: reserve, consume, unreserve, availability
  test_production.py          # 14 tests: create, full/partial release, cancel+unreserve
  test_purchasing.py          # 12 tests: issue PO, wallet/capacity constraints, catalog
  test_simulation.py          # 17 tests: demand gen, expiry+penalty, costs, game over
  test_api.py                 # 43 tests: all HTTP endpoints (integration)

start.sh                      # Builds frontend → starts Supplier API → starts Factory API
stop.sh                       # Kills all services
pytest.ini                    # testpaths = tests, asyncio_mode = auto
```

## Data Model

### Factory DB (simulator.db)

| Table | Purpose |
|-------|---------|
| `game_state` | Singleton: current_day, wallet_balance, capacities, game_over |
| `daily_costs` | Fixed cost, variable cost/unit, energy cost/hour, maintenance % |
| `config` | Key-value runtime config (thresholds, defaults) |
| `clients` | Demand sources (id=1 "Default Client") |
| `products` | Finished printers (type=finished) |
| `raw_materials` | Purchasable inputs with base_price, volume_per_unit |
| `bom` | Bill of Materials: product × material × qty_needed |
| `inventory` | quantity + reserved_quantity per material |
| `manufacturing_orders` | Status: pending → released → completed / cancelled |
| `demand_orders` | Status: open → partial / fulfilled / lost |
| `events` | Append-only audit log (event_type, sim_day, category, details JSON) |

### Supplier DB (supplier.db)

| Table | Purpose |
|-------|---------|
| `suppliers` | name, lead_time_days, reliability |
| `supplier_products` | supplier × material_id × base_unit_cost × daily_price_factor |
| `purchase_orders` | All POs; status: pending → delivered |

### Relationships

```
Client → DemandOrder
Product → ManufacturingOrder, DemandOrder
RawMaterial → BOM → Product
RawMaterial → Inventory
ManufacturingOrder → (BOM lookup) → Inventory (reserve/consume)

[Supplier API]
Supplier → SupplierProduct ← material_id (matches factory RawMaterial.id)
Supplier → PurchaseOrder
```

## Simulation Day Cycle

```
advance_day(db):
  1. supplier_client.fluctuate_prices()          → Supplier API: POST /prices/fluctuate
  2. generate_demand_orders(db, day)             → 1-2 random DemandOrders
  3. supplier_client.get_due_orders(day)         → Supplier API: GET /orders/due?day=N
     → update local Inventory.quantity
     → supplier_client.deliver_order(id, day)    → Supplier API: PUT /orders/{id}/deliver
  4. process_production(db, day)
     → for each released MO (up to daily_production_capacity):
        check BOM availability → consume materials → mark completed
  5. mark_expired_demands(db, day)
     → status="lost", penalty=€50×unfulfilled, deduct from wallet
     → log DEMAND_EXPIRED + PENALTY_DEDUCTED events
  6. calculate_daily_costs(db, day)              → deduct fixed_cost
     → deduct production_stats["cost"] (variable + energy + maintenance)
  7. check_game_over(db, day)
     → wallet < 0: days_with_negative_balance++
     → >= 3 consecutive: game_over = True
  8. current_day += 1
  9. db.commit()
```

## Business Rules

| Rule | Value |
|------|-------|
| Starting wallet | €10,000 (configurable on reset) |
| Daily fixed cost | €500 |
| Variable cost per unit produced | €50 |
| Energy cost per assembly hour | €10 |
| Maintenance | 5% of total daily cost |
| Late/lost demand penalty | €50 per unfulfilled unit |
| Game over trigger | 3 consecutive days with negative wallet |
| Default warehouse capacity | 10,000 units |
| Default production capacity | 10 units/day (configurable on reset) |
| Price fluctuation | ±10% daily (uniform random in [0.90, 1.10]) |
| Demand orders per day | 1–2 (random) |
| Demand due window | 3–7 days from request_day |

## API Endpoints

### Factory API (port 8000)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/game/state | Game state (day, wallet, capacities) |
| GET | /api/game/inventory | Inventory levels per material |
| GET | /api/game/products | Active finished products |
| GET | /api/game/demand-orders | Demand orders (optional ?status=) |
| GET | /api/game/finished-goods | Available finished goods per product |
| GET | /api/game/events | Event log (optional ?category=) |
| POST | /api/game/advance-day | Advance simulation by one day |
| POST | /api/game/demand-orders/{id}/fulfill | Manually serve a demand order |
| GET | /api/game/export | Download full game snapshot as JSON |
| POST | /api/game/import | Restore game from JSON snapshot |
| POST | /api/game/reset | Reset to day 1 (optional config body) |
| GET | /api/manufacturing-orders | List all MOs |
| POST | /api/manufacturing-orders | Create new MO |
| GET | /api/manufacturing-orders/{id} | Get MO with BOM detail |
| PUT | /api/manufacturing-orders/{id}/release | Release MO to production |
| PUT | /api/manufacturing-orders/{id}/cancel | Cancel MO (unreserves materials) |
| GET | /api/suppliers | List suppliers (via Supplier API) |
| GET | /api/suppliers/{id}/catalog | Catalog with current prices |
| GET | /api/suppliers/{id}/pricing/{mat_id} | Single material pricing |
| GET | /api/purchase-orders | List all POs (via Supplier API) |
| POST | /api/purchase-orders | Issue new PO (wallet + capacity check) |

### Supplier API (port 8001)

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /suppliers | List all suppliers |
| GET | /suppliers/{id}/catalog | Catalog with current prices |
| GET | /suppliers/{id}/pricing/{mat_id} | Single material pricing |
| POST | /orders | Create purchase order |
| GET | /orders | List all orders |
| GET | /orders/due?day=N | Orders due on or before day N |
| PUT | /orders/{id}/deliver | Mark order as delivered |
| POST | /prices/fluctuate | Apply ±10% price fluctuation |
| DELETE | /orders | Delete all orders (used by game import/reset) |

## Coding Conventions

### Python
- Type hints on all function signatures
- Pydantic v2 models for all API validation
- Service layer separation: routes handle HTTP, services handle logic
- Custom exceptions: `PurchasingError`, `SimulationError`, `InsufficientFundsError`, etc.
- `supplier_client` calls degrade gracefully (catch `SupplierAPIError`, return 0/pass)

### Tests
- `StaticPool` in-memory SQLite so all connections share same DB
- `mock_supplier_client` autouse fixture in `conftest.py` patches all `supplier_client.*` methods
- `client` fixture patches `app.db.database.engine`, `SessionLocal`, `app.services.seed.SessionLocal`
- No real HTTP calls in any test

### Frontend
- React components in `frontend/src/components/`
- All API calls via `fetch('/api/...')` — relative URL, same origin as the page
- Built with `npm run build` → `frontend/dist/` served by FastAPI's `StaticFiles`
- SPA fallback: all non-`/api` routes return `index.html`

## Running Locally

```bash
# One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Launch
./start.sh        # builds frontend, starts Supplier API + Factory API

# Tests
pytest tests/ -v  # 98 tests, ~4s

# Stop
./stop.sh
```

## Current State

*Last Updated: 2026-05-14*
*All phases complete ✅ — 98/98 tests passing*

### Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation: project structure, DB schema, seeding | ✅ |
| 2 | Core simulation: advance_day, production, purchasing, events | ✅ |
| 3 | Business rules: wallet, capacity, reservations, penalties, game-over | ✅ |
| 4 | Import/Export: JSON snapshot save/load | ✅ |
| 5 | Frontend: React SPA with all tabs, served by FastAPI | ✅ |
| 6 | Testing: 98 tests across 5 files, all passing | ✅ |
| — | Two-server refactor: Supplier API split into standalone service | ✅ |

### Notable Bug Fixes
- Missing `Client` seed record (FK violation on demand generation)
- `check_material_availability` ignored `reserved_quantity` (double-reservation)
- `cancel_manufacturing_order` didn't unreserve materials
- Warehouse capacity double-counted `reserved_quantity` (it's already included in `quantity`)
- `mark_expired_demands` didn't deduct penalties from wallet
- Export/import endpoints still referenced `PurchaseOrder` from factory DB after split
