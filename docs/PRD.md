# 3D Printer Factory Simulator — Product Requirements Document

**Version:** 3.0
**Date:** 2026-05-28
**Status:** Complete — All phases delivered

---

## 1. Executive Summary

### 1.1 Objective

Build a discrete-event simulation system that models the full production cycle of a factory manufacturing 3D printers. The system spans three independent applications — a raw-material Provider, a Manufacturer, and a Retailer — each with its own database, communicating exclusively over HTTP. The user (or an AI agent) acts as production planner at any tier, making decisions about manufacturing, purchasing, pricing, and fulfillment while managing inventory, costs, and capacity. Autonomous AI agents can run all three roles simultaneously, driven by a Turn Engine that advances every app in lockstep one simulated day at a time.

### 1.2 Core Gameplay Loop

```
┌───────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Turn Engine  │───▶│  Demand Injected │───▶│  Agent / User  │
│  advances day │    │  into Retailer   │    │  Decisions     │
└───────────────┘    └──────────────────┘    └────────────────┘
        ▲                                            │
        │                                            ▼
        │    ┌──────────────────┐    ┌───────────────────────┐
        └────│  Events Logged   │◀───│  All Three Apps       │
             │  Metrics Written │    │  Process Their Turn   │
             └──────────────────┘    └───────────────────────┘
```

The game ends at the Manufacturer if its wallet goes negative for 3 consecutive days.

### 1.3 Success Criteria

- Three independently deployable FastAPI apps with separate SQLite databases
- React 19 SPA served by the Manufacturer API, full tab-based UI
- Turn Engine orchestrates all three apps per simulated day
- Three autonomous Claude agents (one per role) run autonomously via `claude --print`
- Two named scenarios (calm-market, holiday-rush) with compound event support
- Per-app metrics tables enable post-run time-series analysis
- `analysis.py` generates four matplotlib charts from metrics databases
- SimDashboard frontend tab with autopilot and scenario selector
- 112 automated tests, all passing

---

## 2. System Architecture

### 2.1 Three-App Design

```
Turn Engine (orchestrator)
  │  reads config/sim.json + scenarios/*.json
  │  advances all three apps in lockstep each turn
  │
  ├─────────────────────────────────────────────────────────────┐
  │                                                             │
  ▼                                                             ▼
Provider API :8001                                    Retailer API :8003
(FastAPI + SQLite: supplier.db)                       (FastAPI + SQLite: retailer.db)
  │                                                             │
  │  raw material orders via supplier_client.py                 │  finished printer orders via retailer purchase client
  ▼                                                             │
Manufacturer API :8002  ◀────────────────────────────────────────┘
(FastAPI + SQLite: simulator.db)
  │  serves React 19 SPA at /
  └─ /api/* routes
```

No app touches another app's database directly. All cross-service communication goes through HTTP clients.

### 2.2 Port and Database Assignment

| App | Port | Database | Role |
|-----|------|----------|------|
| Provider | 8001 | supplier.db | Raw material supplier |
| Manufacturer | 8002 | simulator.db | Factory production |
| Retailer | 8003 | retailer.db | End-customer retail |

### 2.3 File Structure

```
app/                          # Manufacturer API (port 8002)
  main.py                     # FastAPI app; serves React build + /api/* routes
  db/
    database.py               # Engine, SessionLocal, Base, get_db, init_db
    models.py                 # All ORM models including ManufacturerMetrics
  schemas/                    # Pydantic v2 request/response schemas
  services/
    simulation.py             # advance_day(), demand gen, production, costs, game-over
    production.py             # create_mo(), release_mo(), cancel_mo()
    purchasing.py             # issue_purchase_order(), supplier catalog helpers
    inventory.py              # reserve/consume/unreserve materials
    supplier_client.py        # HTTP client for Provider API (httpx, sync)
    seed.py                   # seed_initial_data(), reset_game()
  api/
    game.py                   # /api/game/* endpoints
    manufacturing.py          # /api/manufacturing-orders/* endpoints
    purchasing.py             # /api/suppliers/*, /api/purchase-orders endpoints
    sales.py                  # /api/sales-orders/* endpoints
    agent.py                  # /api/agent/context
    dashboard.py              # /api/dashboard/state + /api/dashboard/run-turn

supplier_api/                 # Provider API (port 8001)
  main.py
  database.py
  models.py                   # Supplier, SupplierProduct, PricingTier, Stock,
                              #   PurchaseOrder, SimState, SupplierEvent, ProviderMetrics
  routes.py                   # All inter-service + CLI/agent endpoints
  seed.py

retailer/                     # Retailer API (port 8003)
  main.py
  database.py
  models.py                   # Catalog, CustomerOrder, RetailerPurchaseOrder,
                              #   RetailerStock, RetailerGameState, RetailerEvent,
                              #   RetailerMetrics
  seed.py
  schemas.py
  config.py
  api/
    catalog.py
    orders.py
    purchases.py
    game.py
    agent.py                  # /api/agent/context

turn_engine/                  # Turn Engine package
  engine.py                   # Main loop + generate_customer_orders()
  config.py                   # load_scenario(), todays_signal(), compound event logic
  demand.py                   # Stochastic demand injection

frontend/
  src/
    components/
      GameHeader.jsx
      GameTabs.jsx
      Toast.jsx
      Tabs/
        GameTab.jsx
        OrdersTab.jsx
        InventoryTab.jsx
        SuppliersTab.jsx
        EventsTab.jsx
        SimDashboard.jsx      # Three-app dashboard with autopilot
    utils/
      api.js
      formatting.js
  dist/                       # Production build (served by Manufacturer API)

tests/
  conftest.py
  test_inventory.py           # 12 tests
  test_production.py          # 14 tests
  test_purchasing.py          # 12 tests
  test_simulation.py          # 17 tests
  test_api.py                 # 43 tests
  test_retailer.py            # 14 tests

scenarios/
  smoke-test.json
  calm-market.json
  holiday-rush.json

skills/
  manufacturer-manager.md
  provider-manager.md
  retail-manager.md

config/
  sim.json

analysis.py                   # Post-run matplotlib chart generation
turn_engine.py                # Turn Engine entry point
manufacturer_cli.py
provider_cli.py
retailer_cli.py
manufacturer_config.json      # Provider URL (read by supplier_client.py)
retailer_config.json          # Manufacturer URL (read by retailer purchase client)
seed-provider.json
start.sh / stop.sh
```

---

## 3. Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python 3.12 | All three backend apps |
| Backend Framework | FastAPI + Pydantic v2 | REST API, automatic OpenAPI docs |
| Database | SQLite (three separate files) | ACID compliance, easy backup |
| ORM | SQLAlchemy | Declarative models |
| HTTP client | httpx (sync) | Cross-service calls |
| Frontend | React 19 + Vite 5 + TailwindCSS v3 | Built SPA served as static files by Manufacturer API |
| Frontend icons | lucide-react | Icon set used in SimDashboard |
| Charts (post-run) | matplotlib + numpy | `analysis.py` offline charts |
| Simulation | Custom discrete-event loop | Turn-based day progression |
| AI agents | `claude --print` CLI | One agent per role per turn |
| Tests | pytest + httpx | 112 tests, StaticPool in-memory SQLite |

### 3.1 Why Custom Simulation Over SimPy?

Turn-based "Advance Day" mechanics map more naturally to a custom event loop:
- Day boundaries are explicit game checkpoints, not observation points
- User/agent decisions happen at specific points between phases
- Simpler to audit, test, and explain

---

## 4. Data Model

### 4.1 Manufacturer Database (simulator.db)

| Table | Purpose |
|-------|---------|
| `game_state` | Singleton: current_day, wallet_balance, capacities, game_over |
| `daily_costs` | Fixed cost, variable cost/unit, energy cost/hour, maintenance % |
| `config` | Key-value runtime config |
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

#### Key ORM Models

```python
# GameState — singleton row (id=1)
current_day: int
wallet_balance: float          # starts €10,000
warehouse_capacity: int        # default 10,000 units
daily_production_capacity: int # default 10 units/day
days_with_negative_balance: int
game_over: bool

# ManufacturingOrder
status: "pending" | "released" | "completed" | "cancelled"
remaining_qty: int             # tracks partial completion

# DemandOrder
due_day: int                   # request_day + 3–7 days
status: "open" | "partial" | "fulfilled" | "lost"
penalty_amount: float          # €50/unit if lost

# SalesOrder  (B2B from Retailer)
status: "pending" | "fulfilled" | "cancelled"

# ManufacturerMetrics
sim_day: int
parts_stock_json: str          # JSON: {material_name: qty}
finished_stock_json: str       # JSON: {product_name: qty}
production_utilisation: float  # 0.0–1.0
wallet_balance: float
```

### 4.2 Provider Database (supplier.db)

| Table | Purpose |
|-------|---------|
| `suppliers` | name, lead_time_days, reliability |
| `supplier_products` | supplier × material_id × base_unit_cost × daily_price_factor |
| `pricing_tiers` | 4 tiers per supplier_product (1/10/50/100 units: 0%/10%/18%/25% discount) |
| `stock` | Current units held per supplier_product (replenishes +15/day, max 500) |
| `purchase_orders` | All POs; status: pending → shipped → delivered → received (+ delayed) |
| `sim_state` | Key-value store for supplier current_day |
| `supplier_events` | Audit log |
| `provider_metrics` | Daily snapshots: stock per product, prices, order counts |

Stochastic delivery: when an order is due, `random() < reliability` determines on-time delivery. Failure extends `expected_delivery_day` by 1–3 days and sets status to `delayed`.

### 4.3 Retailer Database (retailer.db)

| Table | Purpose |
|-------|---------|
| `catalog` | Products the retailer sells (linked to manufacturer product_id, retail_price) |
| `customer_orders` | End-customer orders (status: open → fulfilled / lost) |
| `retailer_purchase_orders` | B2B POs sent to Manufacturer (status: pending → delivered) |
| `retailer_stock` | On-hand finished printer inventory per catalog item |
| `retailer_game_state` | Singleton: current_day, wallet_balance, game_over |
| `retailer_events` | Append-only audit log |
| `retailer_metrics` | Daily snapshots: stock per model, prices, orders placed/fulfilled/backordered |

---

## 5. Simulation Day Cycle

Each `advance_day()` call on the Manufacturer executes the following phases in order:

```
1. supplier_client.fluctuate_prices()          → Provider: POST /prices/fluctuate
2. supplier_client.advance_supplier_day()      → Provider: POST /api/day/advance
     → pending orders → shipped
     → shipped/delayed orders due today: reliability roll
        success → delivered; failure → delayed (+1–3 days)
     → stock replenished (+15/day, max 500)
     → provider current_day += 1
3. generate_demand_orders(db, day)             → 1–2 random DemandOrders
4. process_purchase_deliveries(db, day)
     → GET /orders/due?day=N (status=delivered)
     → update local Inventory.quantity
     → update LocalPurchaseOrder.status = "delivered"
     → PUT /orders/{id}/deliver (→ received)
5. process_production(db, day)
     → for each released MO (up to daily_production_capacity):
        check BOM availability → consume materials → mark completed
6. mark_expired_demands(db, day)
     → status="lost", penalty=€50×unfulfilled, deduct from wallet
7. calculate_daily_costs(db, day)
     → deduct fixed_cost + production costs (variable + energy + maintenance)
8. check_game_over(db, day)
     → wallet < 0: days_with_negative_balance++
     → >= 3 consecutive: game_over = True
9. current_day += 1; db.commit()
```

Retailer day advancement (called separately by Turn Engine or Dashboard):

```
POST /api/day/advance (Retailer)
  → process incoming Manufacturer deliveries → increment stock, fulfill backorders
  → apply daily operating costs
  → log events; increment current_day
```

---

## 6. API Endpoints

### 6.1 Manufacturer API (port 8002)

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
| GET | /api/suppliers | List suppliers (via Provider API) |
| GET | /api/suppliers/{id}/catalog | Catalog with current prices |
| GET | /api/suppliers/{id}/pricing/{mat_id} | Single material pricing |
| GET | /api/purchase-orders | List all POs |
| POST | /api/purchase-orders | Issue new PO (wallet + capacity check) |
| GET | /api/sales-orders | List all sales orders from Retailer |
| POST | /api/sales-orders | Create new sales order (from Retailer) |
| PUT | /api/sales-orders/{id}/fulfill | Fulfill a sales order |
| GET | /api/agent/context | Full game state snapshot for AI agents |
| GET | /api/dashboard/state | Combined 3-app state snapshot |
| POST | /api/dashboard/run-turn | Run one autopilot turn (inject demand + advance all apps) |
| GET | /api/dashboard/events | Aggregated event logs from all 3 databases |
| GET | /api/dashboard/scenario-events | Scenario event definitions for timeline overlay |

### 6.2 Provider API (port 8001)

**Inter-service endpoints (called by Manufacturer):**

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /suppliers | List all suppliers |
| GET | /suppliers/{id}/catalog | Catalog with current prices + tiers + stock |
| GET | /suppliers/{id}/pricing/{mat_id}?quantity=N | Tier-adjusted pricing |
| POST | /orders | Create purchase order (deducts stock) |
| GET | /orders/due?day=N | Delivered orders awaiting factory acknowledgement |
| PUT | /orders/{id}/deliver | Mark order as received by factory |
| POST | /prices/fluctuate | Apply ±10% price fluctuation |
| POST | /api/day/advance | Advance supplier day |
| DELETE | /orders | Delete all orders (reset/import) |

**CLI/agent endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/catalog | All products with pricing tiers and stock |
| GET | /api/stock | Current stock levels |
| POST | /api/orders | Place order (stock check + tier pricing) |
| GET | /api/orders | List orders (optional ?status=) |
| GET | /api/orders/{id} | Order detail |
| POST | /api/stock/{sp_id}/restock | Add to supplier stock |
| PUT | /api/pricing/tiers/{tier_id} | Update a pricing tier |
| GET | /api/day/current | Current supplier day |
| GET | /api/export | Export supplier state |
| POST | /api/import | Restore supplier state |
| GET | /api/metrics | Provider metrics time-series (stock, prices, orders per sim_day) |
| GET | /api/events | Supplier event log (last 200, optional ?sim_day=N filter) |

### 6.3 Retailer API (port 8003)

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/game/state | Retailer game state (day, wallet, game_over) |
| POST | /api/game/advance-day | Advance retailer simulation by one day |
| GET | /api/game/export | Export retailer snapshot |
| POST | /api/game/import | Restore retailer from JSON snapshot |
| POST | /api/game/reset | Reset retailer to day 1 |
| GET | /api/catalog | List retailer product catalog |
| GET | /api/orders | List customer orders (optional ?status=) |
| POST | /api/orders | Create new customer order |
| PUT | /api/orders/{id}/fulfill | Fulfill a customer order from stock |
| GET | /api/purchases | List B2B purchase orders sent to manufacturer |
| POST | /api/purchases | Issue new B2B purchase order to manufacturer |
| GET | /api/agent/context | Full retailer state snapshot for AI agents |
| GET | /api/metrics | Time-series metrics rows (queried by Dashboard) |
| GET | /api/events | Retailer event log (last 200, optional ?sim_day=N filter) |

---

## 7. Turn Engine Design

### 7.1 Overview

`turn_engine/` is a Python package orchestrated by `turn_engine.py`. It advances all three apps in dependency order (Provider → Manufacturer → Retailer) on each simulated day and injects stochastic customer demand into the Retailer before apps advance.

### 7.2 CLI Invocation

```bash
python turn_engine.py config/sim.json scenarios/holiday-rush.json 25
```

Arguments: config file path, scenario file path, number of days to simulate.

### 7.3 Per-Day Execution Sequence

```
For each simulated day:
  1. inject_demand(retailer)         POST /api/orders — customer orders per scenario profile
  2. retailer_decisions(retailer)    invoke skills/retail-manager.md agent
  3. manufacturer_decisions(mfg)     invoke skills/manufacturer-manager.md agent
  4. provider_decisions(provider)    invoke skills/provider-manager.md agent
  5. advance_provider(provider)      POST /api/day/advance
  6. advance_manufacturer(mfg)       POST /api/game/advance-day
     (this also internally advances provider via supplier_client)
  7. advance_retailer(retailer)      POST /api/game/advance-day
  8. log_day_summary()               write day-NNN-summary.json to logs/
```

### 7.4 Configuration Files

`config/sim.json`:
```json
{
  "apps": {
    "provider":     { "url": "http://localhost:8001" },
    "manufacturer": { "url": "http://localhost:8002" },
    "retailer":     { "url": "http://localhost:8003" }
  },
  "agent_skills": {
    "provider":     "skills/provider-manager.md",
    "manufacturer": "skills/manufacturer-manager.md",
    "retailer":     "skills/retail-manager.md"
  },
  "agent_timeout_seconds": 180,
  "log_dir": "logs"
}
```

### 7.5 Day Summary Log

Each day produces files in `logs/`:
- `day-NNN-retailer.log` — raw agent output for retailer decisions
- `day-NNN-manufacturer.log` — raw agent output for manufacturer decisions
- `day-NNN-provider.log` — raw agent output for provider decisions
- `day-NNN-summary.json` — structured metrics snapshot (wallets, orders, key indicators)

---

## 8. Agent Design

### 8.1 Overview

All three roles are driven by Claude agents invoked via `claude --print`. Agent decision logic is encoded in Markdown skill files under `skills/`. The Turn Engine loads the relevant skill and injects it as system context when invoking the agent, keeping logic version-controlled and separate from the engine.

### 8.2 Agent Invocation Pattern

```bash
claude --print "$(cat skills/manufacturer-manager.md)\n\n## Current Context\n$(curl -s http://localhost:8002/api/agent/context)"
```

- Timeout: 180 seconds per invocation.
- stdout captured to `logs/day-NNN-<role>.log`.
- The agent emits API calls that the Turn Engine executes, or calls APIs directly using tool use in an agentic context.

### 8.3 Skill Files

| File | Role | Core Responsibility |
|------|------|---------------------|
| `skills/manufacturer-manager.md` | Manufacturer agent | Release MOs for open sales orders and demand orders; purchase raw materials when stock is low; prioritise orders by due date; maintain ≥€1,000 wallet buffer |
| `skills/provider-manager.md` | Provider agent | Monitor stock levels; trigger restocks before stockouts; adjust pricing tiers in response to demand signals from the scenario |
| `skills/retail-manager.md` | Retailer agent | Fulfill pending customer orders from stock; purchase printers from Manufacturer when stock falls below threshold; manage wallet |

### 8.4 Agent Context Endpoints

Each app exposes `GET /api/agent/context` returning a single JSON object with complete operational state:

- **Manufacturer**: wallet, inventory with available qty, products + BOM + max producible, open demands with days remaining and revenue, active MOs, pending POs, supplier catalog with per-tier effective prices and affordability flags
- **Retailer**: game state, catalog with stock/prices, open orders, stats (fulfilled/backordered last 5 days), pending purchase orders to Manufacturer
- **Provider**: accessible via `/api/catalog` + `/api/stock` + `/api/orders`

---

## 9. Scenario System

### 9.1 Overview

Scenarios are JSON files in `scenarios/`. Each scenario defines a name, total days, per-day demand quantities, and a list of timed market events. The Turn Engine reads the scenario each tick and computes the active signal for the current day.

### 9.2 Scenario File Format

```json
{
  "scenario_name": "holiday-rush",
  "days": 25,
  "daily_demand": [
    { "sku": "P3D-Classic", "quantity": 3 },
    { "sku": "P3D-Pro",     "quantity": 2 }
  ],
  "events": [
    {
      "name": "Black Friday",
      "description": "Consumer demand spike",
      "start_day": 5,
      "end_day": 8,
      "demand_modifier": 2.5,
      "supply_modifier": 1.0,
      "price_sensitivity": "high"
    },
    {
      "name": "Chip Shortage",
      "description": "Component supply disruption",
      "start_day": 6,
      "end_day": 20,
      "supply_modifier": 0.3,
      "lead_time_modifier": 2.0
    }
  ]
}
```

### 9.3 Compound Event Logic

When multiple events are active simultaneously, numeric modifiers (`demand_modifier`, `supply_modifier`, `lead_time_modifier`) are **multiplied** together. String hints (`price_sensitivity`) use last-writer-wins. This allows realistic compound stress:

| Scenario | Days 6–8 (Black Friday + Chip Shortage) |
|----------|----------------------------------------|
| demand_modifier | 2.5 × 1.0 = 2.5 |
| supply_modifier | 1.0 × 0.3 = 0.3 |
| lead_time_modifier | 1.0 × 2.0 = 2.0 |

### 9.4 Bundled Scenarios

| File | Purpose | Days | Key Events |
|------|---------|------|------------|
| `scenarios/smoke-test.json` | Minimal CI integration test | 3 | None |
| `scenarios/calm-market.json` | Stable baseline (control group) | 25 | None |
| `scenarios/holiday-rush.json` | Volatile stress test | 25 | Black Friday (days 5–8), Chip Shortage (days 6–20), Christmas (days 18–25) |

---

## 10. Metrics and Analysis

### 10.1 Per-App Metrics Tables

Each app snapshots key indicators into its own metrics table on every `advance-day` call. These provide time-series data for post-run analysis.

#### ManufacturerMetrics (simulator.db)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| sim_day | INTEGER | Simulation day |
| parts_stock_json | TEXT | JSON: {material_name: available_qty} |
| finished_stock_json | TEXT | JSON: {product_name: available_qty} |
| production_utilisation | REAL | 0.0–1.0 fraction of capacity used |
| wallet_balance | REAL | End-of-day wallet |

#### ProviderMetrics (supplier.db)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| sim_day | INTEGER | Simulation day |
| stock_json | TEXT | JSON: {material_name: stock_qty} |
| prices_json | TEXT | JSON: {material_name: effective_price} |
| orders_placed | INTEGER | Orders placed this day |
| orders_delivered | INTEGER | Orders delivered this day |

#### RetailerMetrics (retailer.db)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| sim_day | INTEGER | Simulation day |
| printer_stock_json | TEXT | JSON: {model_name: stock_qty} |
| prices_json | TEXT | JSON: {model_name: retail_price} |
| customer_orders_placed | INTEGER | New orders this day |
| customer_orders_fulfilled | INTEGER | Orders fulfilled this day |
| customer_orders_backordered | INTEGER | Active backorders |
| wallet_balance | REAL | End-of-day retailer wallet |

### 10.2 Analysis Pipeline

`analysis.py` is a standalone script that reads all three metrics databases and generates four matplotlib charts.

#### Usage

```bash
python analysis.py [--scenario LABEL] [--output-dir DIR]
```

Expects `simulator.db`, `supplier.db`, and `retailer.db` in the current directory (or override via flags).

#### Chart Types

| Chart | Description |
|-------|-------------|
| **Inventory over Time** | Line chart: parts stock, manufacturer finished stock, retailer printer stock per day |
| **Prices over Time** | Line chart: per-material effective prices at Provider, per-SKU retail prices at Retailer |
| **Order Fulfillment** | Grouped bar chart: orders placed vs fulfilled vs backordered per day at Retailer |
| **Scenario Events Overlay** | Shaded regions on any chart showing active scenario event windows |

#### Side-by-Side Comparison

Running `analysis.py` against two separate scenario snapshots (calm-market vs holiday-rush databases) produces comparable charts illustrating the effect of compound market events on inventory levels, pricing, and fulfillment rates.

---

## 11. Dashboard API and SimDashboard Frontend

### 11.1 Dashboard API (`app/api/dashboard.py`)

Mounted at `/api/dashboard/`, these two endpoints provide a single-call view of all three apps and a one-click simulation turn.

#### GET /api/dashboard/state

Returns combined JSON:

```json
{
  "turn":         { "day": N, "demands_injected": 0, "produced": 0, "deliveries": 0, "expired_demands": 0 },
  "scenario":     { "name": "...", "active_events": [...], "demand_modifier": 1.0, "supply_modifier": 1.0, "lead_time_modifier": 1.0 },
  "manufacturer": { "day": N, "wallet": F, "parts_stock": {...}, "finished_stock": {...}, "utilisation": F, "open_demands": N, "active_mos": N },
  "retailer":     { "day": N, "wallet": F, "stock": {...}, "prices": {...}, "open_orders": N, "fulfilled_orders": N, "backordered": N },
  "provider":     { "day": N, "stock": {...}, "prices": {...}, "pending_orders": N },
  "metrics_history": [ { "day": N, "mfg_wallet": F, "ret_wallet": F, "parts_stock": N, "finished_stock": N, "ret_stock": N, "produced": F, "fulfilled": N, "backordered": N }, ... ]
}
```

Optional query parameter: `?scenario_file=scenarios/holiday-rush.json` to include active scenario signal.

#### POST /api/dashboard/run-turn

Runs one complete simulation turn with autopilot:

1. Load scenario and compute today's signal
2. Inject customer demand into Retailer via `generate_customer_orders()`
3. Autopilot retailer: fulfill pending orders; restock from Manufacturer if stock < 5
4. Autopilot manufacturer: purchase materials if available < 80; create + release MOs for open demand/sales orders; fulfill demand orders and sales orders from finished goods
5. Advance Retailer: `POST /api/game/advance-day`
6. Advance Manufacturer: `advance_day(db)` — this also internally advances Provider
7. Return combined state (same shape as GET /state)

Query parameter: `?scenario_file=scenarios/holiday-rush.json`

### 11.2 SimDashboard Frontend Tab

`frontend/src/components/Tabs/SimDashboard.jsx` is the React tab for monitoring and driving the three-app simulation from the browser.

#### Features

- **Three-panel layout**: Manufacturer card (wallet, parts stock, finished stock, utilisation), Retailer card (wallet, stock per SKU, backordered), Provider card (stock, pending orders)
- **Scenario selector**: dropdown to choose between scenario files
- **Run Turn button**: calls `POST /api/dashboard/run-turn`, updates all three panels
- **Auto-Run toggle**: runs one turn every 3 seconds automatically (uses `setInterval`); Play/Pause button with Lucide icons
- **Turn result display**: shows demands injected, units produced, deliveries, expired demands, autopilot actions per turn
- **Active events display**: lists scenario events active on the current day with their modifiers
- **Metrics history table**: scrollable table of last 30 days showing wallet balances, stock levels, fulfillment counts
- **Reset button**: calls `POST /api/game/reset` on Manufacturer to start a fresh run

#### Charts

- **Inventory Over Time**: 3 lines — parts stock, manufacturer finished goods, retailer stock
- **Prices Over Time**: 3 lines — provider average price, manufacturer wholesale price, retailer retail price
- **Order Fulfillment**: daily grouped bars — placed vs fulfilled vs backordered
- **Scenario Events Timeline**: colored bands per active scenario event overlaid on the time axis
- **Event Logs Viewer**: collapsible panel aggregating event logs from all 3 databases (provider, manufacturer, retailer)

---

## 12. Business Rules

| Rule | Value |
|------|-------|
| Starting wallet (Manufacturer) | €10,000 (configurable on reset) |
| Starting wallet (Retailer) | €50,000 (configurable on reset) |
| Daily fixed cost | €500 |
| Variable cost per unit produced | €50 |
| Energy cost per assembly hour | €10 |
| Maintenance | 5% of total daily cost |
| Late/lost demand penalty | €50 per unfulfilled unit |
| Game over trigger | 3 consecutive days with negative wallet (Manufacturer) |
| Default warehouse capacity | 10,000 units |
| Default production capacity | 10 units/day (configurable on reset) |
| Price fluctuation | ±10% daily (uniform random in [0.90, 1.10]) |
| Demand orders per day | 1–2 (random, from Manufacturer's own demand generation) |
| Demand due window | 3–7 days from request_day |
| Pricing tiers | 1+ units: base; 10+: −10%; 50+: −18%; 100+: −25% |
| Supplier reliability | Probability of on-time delivery; failure → 1–3 day delay |
| Supplier stock replenishment | +15 units/day per product, max 500 |
| Material reservation | Reserved when MO is released; consumed on completion; unreserved on cancel |
| Finished goods accounting | Computed on-the-fly: completed MO qty − fulfilled demand qty − shipped sales qty |

---

## 13. Acceptance Criteria

### Delivered (All Phases Complete)

- [x] Three independently deployable FastAPI apps on ports 8001, 8002, 8003
- [x] Separate SQLite databases — no cross-DB queries
- [x] React 19 + Vite 5 + TailwindCSS v3 SPA served by Manufacturer API
- [x] Full simulation day cycle with all 9 phases executing correctly
- [x] Material reservation model prevents double-allocation
- [x] Partial order release (release N < MO.quantity splits the MO)
- [x] Wallet enforcement: no overdraft on purchase orders
- [x] Warehouse capacity enforcement
- [x] Game over after 3 consecutive days with negative wallet
- [x] Import/export of full game state as JSON for all three apps
- [x] Quantity-based pricing tiers (4 tiers per supplier-product)
- [x] Stochastic delivery delays based on supplier reliability
- [x] Retailer app with customer order lifecycle and B2B purchase orders to Manufacturer
- [x] SalesOrder model on Manufacturer side for B2B inbound orders
- [x] Turn Engine orchestrates all three apps in dependency order per day
- [x] Three agent skill files (provider, manufacturer, retailer)
- [x] `claude --print` agent invocation from Turn Engine
- [x] Two named scenarios: calm-market and holiday-rush
- [x] Compound scenario event modifiers (multiply numeric modifiers)
- [x] ManufacturerMetrics, ProviderMetrics, RetailerMetrics tables written on every advance-day
- [x] `analysis.py` generates four chart types from all three metrics databases
- [x] Dashboard API (`/api/dashboard/state` and `/api/dashboard/run-turn`)
- [x] SimDashboard frontend tab with auto-run, scenario selector, three-app panels
- [x] 112 automated tests, all passing

---

## 14. Appendix

### A. Initial Seed Data

#### Products (Manufacturer)

| id | name | type | sell_price | assembly_time_hours |
|----|------|------|------------|---------------------|
| 1 | P3D-Classic | finished | 699.00 | 2.0 |
| 2 | P3D-Pro | finished | 1299.00 | 4.0 |

#### Raw Materials

| id | name | base_price |
|----|------|------------|
| 1 | ABS Filament Spool (1kg) | 25.00 |
| 2 | PLA Filament Spool (1kg) | 22.00 |
| 3 | Aluminum Extrusion 1m | 15.00 |
| 4 | Steel Rod 5mm | 8.00 |
| 5 | Stepper Motor NEMA17 | 18.00 |
| 6 | Linear Rail 200mm | 12.00 |
| 7 | Control Board v2.1 | 45.00 |
| 8 | Hotend Assembly | 35.00 |

#### Suppliers (Provider)

| id | name | lead_time_days | reliability |
|----|------|----------------|-------------|
| 1 | Industrial Materials Co. | 3 | 0.95 |
| 2 | QuickShip Components | 1 | 0.85 |
| 3 | Global Sourcing Ltd | 7 | 0.98 |

Each supplier carries all 8 materials, with 4 pricing tiers per supplier-product (96 total tier rows) and starting stock of 500 units per product.

#### Default Daily Costs

```json
{
  "fixed_cost": 500.00,
  "variable_cost_per_unit": 50.00,
  "energy_cost_per_hour": 10.00,
  "maintenance_percentage": 0.05
}
```

### B. Glossary

| Term | Definition |
|------|------------|
| BOM | Bill of Materials — list of raw materials needed per finished product unit |
| Lead Time | Days between issuing a purchase order and receiving materials |
| DemandOrder | Stochastic customer request generated by the Manufacturer's own demand engine |
| SalesOrder | B2B order placed by the Retailer on the Manufacturer |
| ManufacturingOrder | Internal work order to produce finished goods |
| LocalPurchaseOrder | Manufacturer-side mirror of every PO placed with the Provider |
| Compound Event | Two or more scenario events active simultaneously; numeric modifiers multiply |
| Autopilot | Rule-based decision logic in `_autopilot_manufacturer` and `_autopilot_retailer` in `dashboard.py` that runs when `POST /api/dashboard/run-turn` is called |
| Turn Engine | External Python orchestrator (`turn_engine.py`) that advances all three apps per simulated day |
| Agent Context | Single-call JSON snapshot at `/api/agent/context` that gives an AI agent all information needed to make decisions for the current turn |

---

*Document Version: 3.0*
*Last Updated: 2026-05-28*
*Status: Complete — All phases delivered*
