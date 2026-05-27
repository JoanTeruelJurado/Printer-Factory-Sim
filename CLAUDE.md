# Project: 3D Printer Production Simulator

## What This Is
A discrete-event simulation system that models the full production cycle of a factory manufacturing 3D printers. The user acts as production planner, making decisions about what to manufacture and what materials to purchase while managing inventory, costs, and production capacity. The game ends if the wallet goes negative for 3 consecutive days.

## Tech Stack
- **Python 3.12** — Provider API + Manufacturer API + Retailer API + Turn Engine
- **FastAPI + Pydantic v2** — REST API with automatic OpenAPI documentation
- **React 19 + Vite 5 + TailwindCSS v3** — Frontend SPA, built and served by the Manufacturer API
- **SQLite** — Three separate databases: `simulator.db` (manufacturer), `supplier.db` (provider), `retailer.db` (retailer)
- **SQLAlchemy ORM** — Database access layer
- **httpx** — Synchronous HTTP client used by `supplier_client.py` and retailer purchase client
- **pytest + httpx** — Test suite (112 tests, 6 files)
- **Custom discrete-event loop** — Turn-based day progression orchestrated by Turn Engine

## Architecture

### Three-App Design

```
Turn Engine (orchestrator)
  │  reads config/sim.json + scenarios/*.json
  │  advances all three apps in lockstep each turn
  │
  ├──────────────────────────────────────────────────────────┐
  │                                                          │
  ▼                                                          ▼
Provider API :8001  (FastAPI + SQLite: supplier.db)     Retailer API :8003  (FastAPI + SQLite: retailer.db)
  │                                                          │
  ├── GET  /suppliers                                        ├── /api/game/*           game state, advance day
  ├── GET  /suppliers/{id}/catalog                          ├── /api/catalog/*         product catalog management
  ├── GET  /suppliers/{id}/pricing/{material_id}[?qty=N]   ├── /api/orders/*          customer order lifecycle
  ├── POST /orders                                          ├── /api/purchases/*       purchase orders to manufacturer
  ├── GET  /orders, /orders/due?day=N                       └── /api/agent/context     full state for AI agents
  ├── PUT  /orders/{id}/deliver
  ├── POST /prices/fluctuate
  ├── POST /api/day/advance
  ├── GET  /api/catalog, /api/stock, /api/orders, /api/day/current
  ├── POST /api/stock/{sp_id}/restock
  ├── PUT  /api/pricing/tiers/{tier_id}
  ├── GET  /api/export, POST /api/import
  └── DELETE /orders

  ▲                                                          ▲
  │  HTTP via supplier_client.py                             │  HTTP via retailer purchase client
  │  (URL from manufacturer_config.json)                     │  (URL from retailer_config.json)
  ▼                                                          │
Manufacturer API :8002  (FastAPI + SQLite: simulator.db) ───┘
  │  serves React build at /
  │  exposes /api/* routes
  │
  ├── /api/game/*                   game state, advance day, export/import
  ├── /api/manufacturing-orders/*   MO lifecycle
  ├── /api/sales-orders/*           sales orders from retailer
  ├── /api/suppliers, /api/purchase-orders
  └── /api/agent/context            full state snapshot for AI agents
```

No app touches another app's database directly. All cross-service communication goes through HTTP clients. The Turn Engine is the sole orchestrator that advances days across all three services.

### Key Architecture Decisions

1. **Three-App Split**: Provider (raw materials), Manufacturer (production), and Retailer (sales to end customers) each run as independent FastAPI apps with their own SQLite databases. No app reads another's DB directly.

2. **supplier_client.py**: Thin HTTP wrapper around all Provider API calls. Raises `SupplierAPIError` on connection failure. Both `process_purchase_deliveries` and `apply_daily_price_fluctuation` degrade gracefully if the Provider API is down.

3. **React SPA served by FastAPI**: The React build (`frontend/dist/`) is served as static files by the Manufacturer API. No separate dev server in production. `spa_fallback` route returns `index.html` for all non-API paths.

4. **Custom Simulation Engine**: Turn-based day progression with explicit boundaries. Each `advance_day()` call runs: price fluctuation → demand generation → purchase deliveries → production → expire demands + apply penalties → deduct costs → game-over check.

5. **Service Layer Pattern**: Routes handle HTTP; services handle business logic. Testable without HTTP overhead.

6. **Singleton Game State**: Only one game instance at a time. `game_state` table has `id = 1`.

7. **Event-Sourced Logging**: All state changes logged to `events` table with JSON `details`. 14+ event types.

8. **Manual Demand Fulfillment**: Revenue is NOT collected automatically. The player must serve each demand order via the UI. On-time → full revenue. Late → no revenue. Expired → €50/unit penalty deducted from wallet.

9. **Finished Goods Accounting**: Available stock = sum of completed MO quantities − already-fulfilled demand quantities. Computed on-the-fly; no separate finished-goods table.

10. **Material Reservation Model**: Materials are reserved when an MO is released (not consumed). Consumed when production completes. Unreserved on cancel. Prevents double-allocation.

11. **Daily Price Fluctuation**: Provider API recalculates `daily_price_factor` (±10%) on each `POST /prices/fluctuate` call, triggered at the start of every `advance_day`.

12. **Partial Order Handling**: Release N < MO.quantity → splits into a new released MO (N units) + the original shrinks to (quantity − N). `remaining_qty` tracks production progress.

13. **Supplier Auto-Advance**: `advance_day()` calls `supplier_client.advance_supplier_day()` (POST /api/day/advance) automatically. The Turn Engine is the sole driver of day progression across all apps.

14. **Quantity-Based Pricing Tiers**: 4 tiers per supplier-product (1/10/50/100 units: 0%/10%/18%/25% discount). `_compute_tier_price()` in supplier routes selects the best applicable tier. Factory passes `quantity` to pricing endpoint so the correct tier price is used for wallet check and deduction.

15. **Stochastic Delivery Delays**: When an order is due, `random() < reliability` decides delivery. On failure: status → `delayed`, `expected_delivery_day` += randint(1,3). Delayed orders retry on subsequent days.

16. **Supplier Stock Management**: Stock deducted at order creation. Replenished 15 units/day (max 500) each `POST /api/day/advance`. Factory checks stock before placing order (UI + API).

17. **Local Purchase Order Tracking**: Factory's `simulator.db` has a `purchase_orders` table (`LocalPurchaseOrder`) mirroring every PO placed (status: pending → delivered). Created by `issue_purchase_order`, updated by `process_purchase_deliveries`. Cleared on reset/import.

18. **Manufacturer Config File**: `manufacturer_config.json` at project root declares the provider URL. `supplier_client.py` reads it on startup; `SUPPLIER_API_URL` env var overrides.

19. **Agent Context Endpoint**: `GET /api/agent/context` returns a single JSON with complete game state for AI agents: wallet, inventory with available qty, products + BOM + max producible, open demands + days remaining + revenue, active MOs, pending POs, supplier catalog with per-tier effective prices and affordability constraints.

20. **Turn Engine Orchestration** (Week 7): `turn_engine/` package drives the multi-app simulation. Each tick it calls advance-day on all three services in dependency order (Provider → Manufacturer → Retailer), injects stochastic demand into the Retailer, and logs cross-service events. Scenario files (`scenarios/*.json`) parameterise initial conditions and demand profiles.

21. **Skill-Based Agents** (Week 7): Agent behaviour is encoded in Markdown skill files (`skills/manufacturer-manager.md`). The Turn Engine loads the relevant skill and injects it as system context when invoking AI agents, keeping agent logic version-controlled and separate from engine code.

22. **Three-DB Isolation** (Week 7): `retailer.db` is owned exclusively by the Retailer API. The Retailer purchases finished printers from the Manufacturer via HTTP (mirroring the Manufacturer↔Provider pattern). `RetailerPurchaseOrder` in `retailer.db` mirrors every B2B order placed, and `CustomerOrder` tracks end-customer sales.

23. **Three Autonomous Agents** (Week 8): All three roles (provider, manufacturer, retailer) have skill files in `skills/`. The Turn Engine invokes `claude --print` for each role per day, passing market signals and game context. Agents make CLI decisions independently; coordination emerges through shared world state (databases).

24. **Compound Scenario Events** (Week 8): Overlapping scenario events multiply numeric modifiers (`demand_modifier`, `supply_modifier`, `lead_time_modifier`). String hints (`price_sensitivity`) use last-writer-wins. This enables realistic compound stress (e.g., chip shortage during Christmas = demand 3.75x, supply 0.24x).

25. **Per-App Metrics Tables** (Week 8): Each app snapshots key indicators (stock, prices, order counts, wallet) into a `*_metrics` table on every `advance-day`. These time-series are queryable by `sim_day` and plotted by `analysis.py` for post-run analysis.

26. **Analysis Pipeline** (Week 8): `analysis.py` reads all three metrics tables and generates four matplotlib charts: inventory over time, prices over time, order fulfillment bars, and scenario events overlay. Supports side-by-side comparison of calm vs volatile scenarios.

## File Structure

```
app/                          # Manufacturer API (port 8002)
  main.py                     # FastAPI app; serves React build + /api/* routes
  db/
    database.py               # Engine, SessionLocal, Base, get_db, init_db
    models.py                 # ORM: GameState, DailyCosts, Config, Client,
                              #   Product, RawMaterial, BOM, Inventory,
                              #   ManufacturingOrder, DemandOrder, SalesOrder,
                              #   Event, LocalPurchaseOrder, ManufacturerMetrics
  schemas/
    __init__.py
    inventory.py              # InventoryItemResponse
    manufacturing.py          # ManufacturingOrderResponse, BOMLineResponse, etc.
    order.py                  # GameStateResponse
    purchase.py               # PricingTierResponse, CatalogItemResponse, etc.
  services/
    simulation.py             # advance_day(), generate_demand_orders(),
                              #   process_production(), mark_expired_demands(),
                              #   calculate_daily_costs(), check_game_over()
    production.py             # create_mo(), release_mo(), cancel_mo()
    purchasing.py             # issue_purchase_order(), list_suppliers(),
                              #   get_supplier_catalog(), list_purchase_orders()
    inventory.py              # reserve_materials(), consume_materials(),
                              #   unreserve_materials(), check_material_availability()
    supplier_client.py        # HTTP client for Provider API (httpx, sync);
                              #   reads manufacturer_config.json for base URL
    seed.py                   # seed_initial_data(), reset_game()
  api/
    game.py                   # /api/game/* endpoints
    manufacturing.py          # /api/manufacturing-orders/* endpoints
    purchasing.py             # /api/suppliers/*, /api/purchase-orders endpoints
    sales.py                  # /api/sales-orders/* endpoints
    agent.py                  # /api/agent/context — full state for AI agents

supplier_api/                 # Provider API (standalone, port 8001)
  main.py                     # FastAPI app; calls init_db() + seed() on startup
  database.py                 # Engine for supplier.db
  models.py                   # Supplier, SupplierProduct, PricingTier, Stock,
                              #   PurchaseOrder, SimState, SupplierEvent
  routes.py                   # Inter-service endpoints (/suppliers, /orders, /prices/*)
                              #   + CLI/agent endpoints (/api/catalog, /api/stock, …)
  seed.py                     # 3 suppliers, 8 materials, 24 SupplierProducts,
                              #   96 pricing tiers (4 per product), stock 500 each

retailer/                     # Retailer API (standalone, port 8003)
  main.py                     # FastAPI app; calls init_db() + seed() on startup
  database.py                 # Engine for retailer.db
  models.py                   # Catalog, CustomerOrder, RetailerPurchaseOrder,
                              #   RetailerStock, RetailerGameState, RetailerEvent
  seed.py                     # Seed retailer catalog + starting state
  schemas.py                  # Pydantic v2 request/response schemas
  config.py                   # Settings; reads retailer_config.json for manufacturer URL
  api/
    catalog.py                # /api/catalog/* — product listing and pricing
    orders.py                 # /api/orders/* — customer order lifecycle
    purchases.py              # /api/purchases/* — B2B purchase orders to manufacturer
    game.py                   # /api/game/* — game state, advance day, export/import

turn_engine/                  # Turn Engine package (orchestrator)
  engine.py                   # Main loop: advance all three apps per tick
  config.py                   # Load config/sim.json and scenario files
  demand.py                   # Stochastic demand injection into Retailer

frontend/
  src/
    components/               # React components
    utils/                    # api.js helpers, constants.js
  dist/                       # Production build (served by Manufacturer API)

tests/
  conftest.py                 # StaticPool in-memory SQLite; supplier_client autouse mock;
                              #   engine/db/client fixtures
  test_inventory.py           # 12 tests: reserve, consume, unreserve, availability
  test_production.py          # 14 tests: create, full/partial release, cancel+unreserve
  test_purchasing.py          # 12 tests: issue PO, wallet/capacity constraints, catalog
  test_simulation.py          # 17 tests: demand gen, expiry+penalty, costs, game over
  test_api.py                 # 43 tests: all HTTP endpoints (integration)
  test_retailer.py            # 14 tests: retailer orders, purchases, catalog, game state

config/
  sim.json                    # Default simulation parameters (days, capacity, costs)

scenarios/
  smoke-test.json             # Minimal scenario for CI integration tests
  calm-market.json            # 25-day stable baseline (control group)
  holiday-rush.json           # 25-day volatile: Black Friday + chip shortage + Christmas

skills/
  manufacturer-manager.md     # Agent skill: manage manufacturer production + purchasing
  provider-manager.md         # Agent skill: manage provider stock + pricing
  retail-manager.md           # Agent skill: manage retailer fulfillment + purchasing + pricing

analysis.py                   # Post-run chart generation (matplotlib) from metrics DBs
manufacturer_cli.py           # CLI for Manufacturer API (manufacturer-cli entrypoint)
manufacturer-cli              # Executable wrapper for manufacturer_cli.py
provider_cli.py               # CLI for Provider API (provider-cli entrypoint)
provider-cli                  # Executable wrapper for provider_cli.py
retailer_cli.py               # CLI for Retailer API (retailer-cli entrypoint)
retailer-cli                  # Executable wrapper for retailer_cli.py
turn_engine.py                # Entry point for Turn Engine (turn-engine entrypoint)
manufacturer_config.json      # Provider URL config read by supplier_client.py
retailer_config.json          # Manufacturer URL config read by retailer purchase client
seed-provider.json            # Reproducible starting state for Provider API
start.sh                      # Builds frontend → starts Provider, Manufacturer, Retailer APIs
stop.sh                       # Kills all services
pytest.ini                    # testpaths = tests, asyncio_mode = auto
```

## Data Model

### Manufacturer DB (simulator.db)

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
| `sales_orders` | B2B orders from Retailer (status: pending → fulfilled / cancelled) |
| `purchase_orders` | Local mirror of POs placed (status: pending / delivered) |
| `events` | Append-only audit log (event_type, sim_day, category, details JSON) |
| `manufacturer_metrics` | Daily snapshots: parts stock, finished stock, utilisation, prices, wallet |

### Provider DB (supplier.db)

| Table | Purpose |
|-------|---------|
| `suppliers` | name, lead_time_days, reliability |
| `supplier_products` | supplier × material_id × base_unit_cost × daily_price_factor |
| `pricing_tiers` | supplier_product × min_quantity × unit_price (4 tiers per product) |
| `stock` | Current units held per supplier_product (replenishes 15/day, max 500) |
| `purchase_orders` | All POs; status: pending → shipped → delivered → received (+ delayed) |
| `sim_state` | Key-value store for supplier current_day |
| `supplier_events` | Supplier-side audit log (order_placed, order_shipped, order_delivered, order_delayed, price_changed, day_advanced, stock_updated) |
| `provider_metrics` | Daily snapshots: stock per product, prices, order counts |

### Retailer DB (retailer.db)

| Table | Purpose |
|-------|---------|
| `catalog` | Products the retailer sells (linked to manufacturer product_id, retail_price) |
| `customer_orders` | End-customer orders (status: open → fulfilled / lost) |
| `retailer_purchase_orders` | B2B POs sent to Manufacturer (status: pending → delivered) |
| `retailer_stock` | On-hand finished printer inventory per catalog item |
| `retailer_game_state` | Singleton: current_day, wallet_balance, game_over |
| `retailer_events` | Append-only audit log for retailer-side events |
| `retailer_metrics` | Daily snapshots: stock per model, prices, orders placed/fulfilled/backordered |

### Relationships

```
Client → DemandOrder
Product → ManufacturingOrder, DemandOrder, SalesOrder
RawMaterial → BOM → Product
RawMaterial → Inventory
ManufacturingOrder → (BOM lookup) → Inventory (reserve/consume)
SalesOrder ← Retailer API (HTTP)

[Provider API]
Supplier → SupplierProduct ← material_id (matches manufacturer RawMaterial.id)
Supplier → PurchaseOrder

[Retailer API]
Catalog → RetailerStock
Catalog → CustomerOrder
RetailerPurchaseOrder → Manufacturer API (HTTP)
```

## Simulation Day Cycle

```
advance_day(db):
  1. supplier_client.fluctuate_prices()          → Supplier API: POST /prices/fluctuate
  2. supplier_client.advance_supplier_day()      → Supplier API: POST /api/day/advance
     → pending orders → shipped
     → shipped/delayed orders due today: reliability roll
        success → delivered; failure → delayed (new due date +1-3 days)
     → supplier stock replenished (+15/day, max 500)
     → supplier current_day += 1
  3. generate_demand_orders(db, day)             → 1-2 random DemandOrders
  4. process_purchase_deliveries(db, day)
     → supplier_client.get_due_orders(day)       → GET /orders/due?day=N (status=delivered)
     → update local Inventory.quantity
     → update LocalPurchaseOrder.status = "delivered"
     → supplier_client.deliver_order(id, day)    → PUT /orders/{id}/deliver (→ received)
  5. process_production(db, day)
     → for each released MO (up to daily_production_capacity):
        check BOM availability → consume materials → mark completed
  6. mark_expired_demands(db, day)
     → status="lost", penalty=€50×unfulfilled, deduct from wallet
     → log DEMAND_EXPIRED + PENALTY_DEDUCTED events
  7. calculate_daily_costs(db, day)              → deduct fixed_cost
     → deduct production_stats["cost"] (variable + energy + maintenance)
  8. check_game_over(db, day)
     → wallet < 0: days_with_negative_balance++
     → >= 3 consecutive: game_over = True
  9. current_day += 1
  10. db.commit()
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
| Pricing tiers | 1+ units: base; 10+: −10%; 50+: −18%; 100+: −25% |
| Supplier reliability | Probability of on-time delivery; failure → 1–3 day delay |
| Supplier stock replenishment | +15 units/day per product, max 500 |

## API Endpoints

### Manufacturer API (port 8002)

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
| GET | /api/purchase-orders | List all POs (via Provider API) |
| POST | /api/purchase-orders | Issue new PO (wallet + capacity check) |
| GET | /api/sales-orders | List all sales orders from Retailer |
| POST | /api/sales-orders | Create new sales order (from Retailer) |
| PUT | /api/sales-orders/{id}/fulfill | Fulfill a sales order |
| GET | /api/agent/context | Full game state snapshot for AI agents |

### Provider API (port 8001)

**Inter-service endpoints (called by Manufacturer API):**

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /suppliers | List all suppliers |
| GET | /suppliers/{id}/catalog | Catalog with current prices + tiers + stock |
| GET | /suppliers/{id}/pricing/{mat_id}?quantity=N | Pricing (tier-adjusted if quantity given) |
| POST | /orders | Create purchase order (deducts stock) |
| GET | /orders | List all orders |
| GET | /orders/due?day=N | Delivered orders awaiting factory acknowledgement |
| PUT | /orders/{id}/deliver | Mark order as received by factory |
| POST | /prices/fluctuate | Apply ±10% price fluctuation |
| POST | /api/day/advance | Advance supplier day (ship pending, deliver due, replenish stock) |
| DELETE | /orders | Delete all orders (used by import/reset) |

**CLI/agent endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/catalog | All products with pricing tiers and stock |
| GET | /api/stock | Current stock levels |
| POST | /api/orders | Place order (stock check + tier pricing, no pre-computed price) |
| GET | /api/orders?status= | List orders with optional status filter |
| GET | /api/orders/{id} | Order detail |
| POST | /api/stock/{sp_id}/restock | Add to supplier stock |
| PUT | /api/pricing/tiers/{tier_id} | Update a pricing tier |
| GET | /api/day/current | Current supplier day |
| GET | /api/export | Export supplier state as JSON |
| POST | /api/import | Restore supplier state from JSON |

### Retailer API (port 8003)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/game/state | Retailer game state (day, wallet, game_over) |
| POST | /api/game/advance-day | Advance retailer simulation by one day |
| GET | /api/game/export | Export retailer snapshot as JSON |
| POST | /api/game/import | Restore retailer from JSON snapshot |
| POST | /api/game/reset | Reset retailer to day 1 |
| GET | /api/catalog | List retailer product catalog with retail prices |
| GET | /api/orders | List customer orders (optional ?status=) |
| POST | /api/orders | Create new customer order |
| PUT | /api/orders/{id}/fulfill | Fulfill a customer order from stock |
| GET | /api/purchases | List B2B purchase orders sent to manufacturer |
| POST | /api/purchases | Issue new B2B purchase order to manufacturer |
| GET | /api/agent/context | Full retailer state snapshot for AI agents |

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
pytest tests/ -v  # 112 tests, ~4s

# Stop
./stop.sh
```

## Current State

*Last Updated: 2026-05-27*
*All phases complete ✅ — 112/112 tests passing*

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
| W6 | Week 6: provider app + manufacturer supply chain integration | ✅ |
| W7 | Week 7: Retailer app, sales orders, turn engine orchestration, agent skills, integration tests | ✅ |
| W8 | Week 8: Three autonomous agents, scenario design, metrics, analysis | ✅ |

### Week 6 Additions
- `manufacturer_cli.py` / `provider_cli.py` — full CLIs for both apps
- `manufacturer_config.json` — declares provider URL (read by `supplier_client.py`)
- `seed-provider.json` — reproducible starting state for Supplier API
- Quantity-based pricing tiers (4 per product, up to 25% discount)
- Stochastic delivery delays based on supplier `reliability` field
- Factory auto-advances supplier day on each `advance_day()` call
- `LocalPurchaseOrder` table in `simulator.db` — local mirror of every PO placed
- `GET /api/agent/context` — single-call full state for AI agents
- Supplier stock deducted at order time, replenished 15/day (max 500)
- Order form validations: stock limit, wallet limit, warehouse capacity limit

### Week 7 Additions
- `retailer/` — standalone Retailer API (port 8003) with own SQLite DB (`retailer.db`)
- `retailer_cli.py` / `retailer-cli` — full CLI for the Retailer API
- `retailer_config.json` — declares manufacturer URL (read by retailer purchase client)
- `turn_engine/` package — `engine.py`, `config.py`, `demand.py` — orchestrates all three apps
- `turn_engine.py` — entry point for the Turn Engine
- `config/sim.json` — default simulation parameters
- `scenarios/smoke-test.json` — minimal scenario for CI integration testing
- `skills/manufacturer-manager.md` — agent skill file for manufacturer production + purchasing decisions
- `SalesOrder` model in `simulator.db` — tracks B2B orders incoming from the Retailer
- `GET /api/sales-orders` + `POST /api/sales-orders` + `PUT /api/sales-orders/{id}/fulfill` on Manufacturer API
- Manufacturer API moved from port 8000 to port 8002
- `test_retailer.py` — 14 new tests covering retailer orders, purchases, catalog, and game state

### Week 8 Additions
- `skills/provider-manager.md` — agent skill for provider stock management + pricing decisions
- `skills/retail-manager.md` — agent skill for retailer fulfillment + purchasing + pricing decisions
- `scenarios/calm-market.json` — 25-day stable baseline scenario (control group)
- `scenarios/holiday-rush.json` — 25-day volatile scenario with 4 overlapping events (Black Friday, chip shortage, Christmas)
- `config/sim.json` updated — all three agent skill files now referenced (provider, manufacturer, retailer)
- Compound event support in `turn_engine/config.py` — overlapping events multiply modifiers (demand, supply, lead_time)
- `ManufacturerMetrics` table in `simulator.db` — daily snapshots of parts stock, finished stock, utilisation, prices, wallet
- `ProviderMetrics` table in `supplier.db` — daily snapshots of stock, prices, order counts
- `RetailerMetrics` table in `retailer.db` — daily snapshots of stock, prices, orders placed/fulfilled/backordered
- Per-turn summary line in engine output: `Day N: X orders / Y fulfilled / Z backordered`
- `analysis.py` — matplotlib chart generation from metrics (inventory, prices, fulfillment, events overlay)
- `retailer/api/agent.py` — `GET /api/agent/context` for retailer (full state snapshot for AI agents)
- Enhanced engine signal display: shows active events, demand/supply/lead_time modifiers per day

### Notable Bug Fixes
- Missing `Client` seed record (FK violation on demand generation)
- `check_material_availability` ignored `reserved_quantity` (double-reservation)
- `cancel_manufacturing_order` didn't unreserve materials
- Warehouse capacity double-counted `reserved_quantity` (it's already included in `quantity`)
- `mark_expired_demands` didn't deduct penalties from wallet
- Export/import endpoints still referenced `PurchaseOrder` from factory DB after split
- Tier 1 was more expensive than base price (1.30× surcharge) — fixed to 1.00×
