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
Browser / AI Agent
  │
  ▼
Factory API :8000  (FastAPI + SQLite: simulator.db)
  │  serves React build at /
  │  exposes /api/* routes
  │
  ├── /api/game/*                   game state, advance day, export/import
  ├── /api/manufacturing-orders/*   MO lifecycle
  ├── /api/suppliers, /api/purchase-orders
  ├── /api/agent/context            full state snapshot for AI agents
  │
  │           HTTP via supplier_client.py (URL from manufacturer_config.json)
  ▼
      Supplier API :8001  (FastAPI + SQLite: supplier.db)
           │
           ├── GET  /suppliers
           ├── GET  /suppliers/{id}/catalog
           ├── GET  /suppliers/{id}/pricing/{material_id}[?quantity=N]
           ├── POST /orders
           ├── GET  /orders, /orders/due?day=N
           ├── PUT  /orders/{id}/deliver
           ├── POST /prices/fluctuate
           ├── POST /api/day/advance    (called by factory advance_day)
           ├── GET  /api/catalog, /api/stock, /api/orders, /api/day/current
           ├── POST /api/stock/{sp_id}/restock
           ├── PUT  /api/pricing/tiers/{tier_id}
           ├── GET  /api/export, POST /api/import
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

13. **Supplier Auto-Advance**: `advance_day()` calls `supplier_client.advance_supplier_day()` (POST /api/day/advance) automatically. The human only needs to advance the manufacturer; the supplier advances in lockstep.

14. **Quantity-Based Pricing Tiers**: 4 tiers per supplier-product (1/10/50/100 units: 0%/10%/18%/25% discount). `_compute_tier_price()` in supplier routes selects the best applicable tier. Factory passes `quantity` to pricing endpoint so the correct tier price is used for wallet check and deduction.

15. **Stochastic Delivery Delays**: When an order is due, `random() < reliability` decides delivery. On failure: status → `delayed`, `expected_delivery_day` += randint(1,3). Delayed orders retry on subsequent days.

16. **Supplier Stock Management**: Stock deducted at order creation. Replenished 15 units/day (max 500) each `POST /api/day/advance`. Factory checks stock before placing order (UI + API).

17. **Local Purchase Order Tracking**: Factory's `simulator.db` has a `purchase_orders` table (`LocalPurchaseOrder`) mirroring every PO placed (status: pending → delivered). Created by `issue_purchase_order`, updated by `process_purchase_deliveries`. Cleared on reset/import.

18. **Manufacturer Config File**: `manufacturer_config.json` at project root declares the provider URL. `supplier_client.py` reads it on startup; `SUPPLIER_API_URL` env var overrides.

19. **Agent Context Endpoint**: `GET /api/agent/context` returns a single JSON with complete game state for AI agents: wallet, inventory with available qty, products + BOM + max producible, open demands + days remaining + revenue, active MOs, pending POs, supplier catalog with per-tier effective prices and affordability constraints.

## File Structure

```
app/                          # Factory API
  main.py                     # FastAPI app; serves React build + /api/* routes
  db/
    database.py               # Engine, SessionLocal, Base, get_db, init_db
    models.py                 # ORM: GameState, DailyCosts, Config, Client,
                              #   Product, RawMaterial, BOM, Inventory,
                              #   ManufacturingOrder, DemandOrder, Event,
                              #   LocalPurchaseOrder
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
    supplier_client.py        # HTTP client for Supplier API (httpx, sync);
                              #   reads manufacturer_config.json for base URL
    seed.py                   # seed_initial_data(), reset_game()
  api/
    game.py                   # /api/game/* endpoints
    manufacturing.py          # /api/manufacturing-orders/* endpoints
    purchasing.py             # /api/suppliers/*, /api/purchase-orders endpoints
    agent.py                  # /api/agent/context — full state for AI agents

supplier_api/                 # Supplier API (standalone, port 8001)
  main.py                     # FastAPI app; calls init_db() + seed() on startup
  database.py                 # Engine for supplier.db
  models.py                   # Supplier, SupplierProduct, PricingTier, Stock,
                              #   PurchaseOrder, SimState, SupplierEvent
  routes.py                   # Inter-service endpoints (/suppliers, /orders, /prices/*)
                              #   + CLI/agent endpoints (/api/catalog, /api/stock, …)
  seed.py                     # 3 suppliers, 8 materials, 24 SupplierProducts,
                              #   96 pricing tiers (4 per product), stock 500 each

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

manufacturer_cli.py           # CLI for Factory API (manufacturer-cli entrypoint)
manufacturer-cli              # Executable wrapper for manufacturer_cli.py
provider_cli.py               # CLI for Supplier API (provider-cli entrypoint)
provider-cli                  # Executable wrapper for provider_cli.py
manufacturer_config.json      # Provider URL config read by supplier_client.py
seed-provider.json            # Reproducible starting state for Supplier API
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
| `purchase_orders` | Local mirror of POs placed (status: pending / delivered) |
| `events` | Append-only audit log (event_type, sim_day, category, details JSON) |

### Supplier DB (supplier.db)

| Table | Purpose |
|-------|---------|
| `suppliers` | name, lead_time_days, reliability |
| `supplier_products` | supplier × material_id × base_unit_cost × daily_price_factor |
| `pricing_tiers` | supplier_product × min_quantity × unit_price (4 tiers per product) |
| `stock` | Current units held per supplier_product (replenishes 15/day, max 500) |
| `purchase_orders` | All POs; status: pending → shipped → delivered → received (+ delayed) |
| `sim_state` | Key-value store for supplier current_day |
| `supplier_events` | Supplier-side audit log (order_placed, order_shipped, order_delivered, order_delayed, price_changed, day_advanced, stock_updated) |

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
| GET | /api/agent/context | Full game state snapshot for AI agents |

### Supplier API (port 8001)

**Inter-service endpoints (called by Factory API):**

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

*Last Updated: 2026-05-15*
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
| W6 | Week 6: provider app + manufacturer supply chain integration | ✅ |

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

### Notable Bug Fixes
- Missing `Client` seed record (FK violation on demand generation)
- `check_material_availability` ignored `reserved_quantity` (double-reservation)
- `cancel_manufacturing_order` didn't unreserve materials
- Warehouse capacity double-counted `reserved_quantity` (it's already included in `quantity`)
- `mark_expired_demands` didn't deduct penalties from wallet
- Export/import endpoints still referenced `PurchaseOrder` from factory DB after split
- Tier 1 was more expensive than base price (1.30× surcharge) — fixed to 1.00×
