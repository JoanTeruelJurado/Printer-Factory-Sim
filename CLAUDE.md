# Project: 3D Printer Production Simulator

## What This Is
A discrete-event simulation system that models the full production cycle of a factory manufacturing 3D printers. The user acts as production planner, making decisions about what to manufacture and what materials to purchase while managing inventory, costs, and production capacity. The game ends if wallet goes negative, creating tension between demand, inventory, capacity, and lead times.

## Tech Stack
- **Python 3.11+** - Readability, extensive libraries, cross-platform
- **FastAPI + Pydantic** - REST API with automatic OpenAPI documentation
- **Vanilla HTML/CSS/JavaScript** - Simple web frontend, no build tools required
- **SQLite** - ACID-compliant persistence with easy backup/export
- **Custom discrete-event loop** - Turn-based day progression (chosen over SimPy for explicit day boundaries)
- **matplotlib** - Chart generation (embedded as base64 PNG in API responses)

## Architecture

### Layer Structure
```
┌─────────────────────────────────────────┐
│          Frontend (static)              │
│    vanilla JS + Fetch API + CSS        │
├─────────────────────────────────────────┤
│            FastAPI Backend              │
│  ┌─────────────┬───────────────────┐   │
│  │   Routes    │  Schemas (Pydantic)│   │
│  ├─────────────┼───────────────────┤   │
│  │  Services   │  (validation)     │   │
│  ├─────────────┼───────────────────┤   │
│  │ Simulation  │                   │   │
│  └─────────────┴───────────────────┘   │
├─────────────────────────────────────────┤
│           SQLite Database               │
│         (via SQLAlchemy ORM)            │
└─────────────────────────────────────────┘
```

### Key Architecture Decisions

1. **Custom Simulation Engine**: Rather than SimPy's continuous event queue, we use a turn-based day progression. Day boundaries are explicit game mechanics where:
   - Demand is generated
   - Purchase orders arrive
   - Production processes up to capacity
   - Costs are calculated
   - All events are logged

2. **Service Layer Pattern**: Business logic is isolated from routes. Simulation rules live in services, making them testable without HTTP overhead.

3. **Singleton Game State**: Only one game instance exists at a time. `game_state` table has `id = 1` constraint.

4. **Event-Sourced Logging**: All state changes logged to `events` table with JSON details. Enables audit trails, replay, analytics.

5. **Material Reservation Model**: When order is released, materials are "reserved" (not immediately consumed). Consumed when production completes. Prevents overselling same material to multiple orders.

6. **Daily Price Fluctuation**: Supplier prices vary ±10% daily. Stored as `daily_price_factor` recalculated each day start.

7. **Partial Order Handling**: Manufacturing orders can be partially released and partially completed. `remaining_qty` tracks progress.

## Data Model

### Core Entities
| Entity | Purpose | Key Relationships |
|--------|---------|-------------------|
| `products` | Finished printers + raw materials | BOM references products (finished) |
| `raw_materials` | Purchasable inputs | BOM references materials |
| `bom` | Material requirements per product | Links products ↔ materials |
| `clients` | Demand sources (randomly generated) | Creates demand_orders |
| `suppliers` | Material sources | Supplies via supplier_products |
| `inventory` | Current stock levels | Tracks all raw_materials |
| `manufacturing_orders` | Production work orders | References products |
| `demand_orders` | Sales requests from clients | References products + clients |
| `purchase_orders` | Supplier orders | References suppliers + materials |
| `events` | Audit log of all actions | Timestamped, categorized |
| `game_state` | Singleton: day, wallet, capacities | — |

### Critical Relationships
```
Client → DemandOrder → (wait fulfillment) → ManufacturingOrder → Product
                                                          ↓
Supplier → PurchaseOrder → Inventory → BOM → (consume) ManufacturingOrder
```

## Coding Conventions

### Python
- **Type hints everywhere** - Function signatures always typed
- **Pydantic models** - All API request/response validation via Pydantic v2
- **Service layer separation** - Routes handle HTTP; services handle business logic
- **Docstrings** - Google-style for all public functions/classes
- **Async/await** - Use `async def` for all route handlers; sync for simulation logic
- **Error handling** - Custom exceptions (`InsufficientFundsError`, `CapacityExceededError`, etc.)
- **File structure**:
  ```
  app/
    __init__.py
    main.py              # FastAPI app instantiation
    db/
      __init__.py
      database.py        # SQLite connection, session management
      models.py          # SQLAlchemy ORM models
    schemas/             # Pydantic models
      __init__.py
      product.py
      order.py
      inventory.py
      ...
    services/            # Business logic
      __init__.py
      simulation.py      # Core simulation engine
      production.py      # Manufacturing logic
      purchasing.py      # Purchase order logic
      demand.py          # Demand generation
      wallet.py          # Financial calculations
    api/                 # Route handlers
      __init__.py
      game.py
      products.py
      orders.py
      ...
    utils/
      __init__.py
      charts.py          # matplotlib helpers
      validators.py
  ```

### Frontend
- **Single HTML file** for simplicity (or modular if needed)
- **Fetch API** for all HTTP calls
- **Base64-encoded PNGs** for chart display
- **Auto-refresh** every 30 seconds via `setInterval`
- **Modal dialogs** for complex forms (Bootstrap or custom)

### API Conventions
- **RESTful naming** - `/api/manufacturing-orders`, not `/api/orders`
- **Standard response format**:
  ```json
  {
    "success": true,
    "data": { /* payload */ },
    "message": null
  }
  ```
- **Error responses**:
  ```json
  {
    "success": false,
    "data": null,
    "message": "Insufficient funds: need €500, have €250",
    "error_code": "INSUFFICIENT_FUNDS"
  }
  ```
- **HTTP status codes** still used semantically (200 OK, 400 Bad Request, 403 Forbidden, 422 Validation, 500 Server Error)

### Configuration
- **Environment variables** via `.env` file (dotenv library):
  ```env
  DATABASE_URL=sqlite:///./simulator.db
  STARTING_WALLET=10000
  WAREHOUSE_CAPACITY=10000
  DAILY_PRODUCTION_CAPACITY=10
  ```
- **Runtime config** stored in `config` table for editable settings

## Current State

### Phase 1: Foundation ✅ COMPLETE (80%)

#### Completed ✅
- [x] PRD document created (900+ lines, comprehensive spec)
- [x] CLAUDE.md initialized with architecture decisions
- [x] Project structure set up (FastAPI app with proper layout)
- [x] Virtual environment & dependencies installed
- [x] Database schema fully implemented (14 SQLAlchemy ORM tables)
- [x] SQLite database initialization working
- [x] Initial data seeding script created
- [x] 3 finished products defined (Hobby, Prosumer, Industrial)
- [x] 8 raw materials defined (filament, extrusions, motors, etc.)
- [x] 3 suppliers configured with lead times & reliability
- [x] GameState initialization (day 1, €10k wallet)
- [x] DailyCosts configuration (€500 fixed, €50/unit, €10/hour)
- [x] Core API endpoints working (6 endpoints, error handling)
- [x] FastAPI app runs without errors
- [x] Frontend skeleton created (5 HTML files)

#### Data Gaps (Intentional - Phase 2) ⚠️
- [ ] Bill of Materials (BOM) - defined in Phase 2 (p2-bom-data)
- [ ] Supplier-material links (SupplierProduct) - defined in Phase 2
- [ ] Initial inventory stock - loaded in Phase 2

#### Not Yet Started ⏳
- [ ] Simulation core (Phase 2)
- [ ] Production service (Phase 2)
- [ ] Purchasing service (Phase 2)
- [ ] Manufacturing order management (Phase 2)
- [ ] Event logging system (Phase 4)
- [ ] Import/export functionality (Phase 4)
- [ ] Frontend UI implementation (Phase 5)
- [ ] Business rule enforcement (Phase 3)
- [ ] Testing suite (Phase 6)

---

### Phase 2: Core Simulation ✅ COMPLETE (11/11 items done)

#### Completed ✅
- [x] BOM data fully defined (20 BOM entries across 3 products)
- [x] Supplier-material pricing set up (24 links with different pricing strategies)
- [x] Initial inventory loaded (150 units of each material for testing)
- [x] Simulation engine core (`app/services/simulation.py` - 620+ lines)
  - advance_day() orchestrator function - fully atomic with transaction support
  - Demand generation (0-5 random orders per day, configurable products)
  - Production processing (materials consumed, goods produced up to capacity)
  - Purchase deliveries (materials arrive based on lead time, added to inventory)
  - Demand fulfillment (FIFO matching of finished goods to sales orders)
  - Daily cost calculation (fixed + variable + energy + maintenance)
  - Game over condition checking (wallet negative for 3+ days)
  - Comprehensive event logging (all state changes logged with JSON details)
- [x] Inventory service (`app/services/inventory.py` - 180+ lines)
  - Material reservation system (reserve when order released)
  - Material consumption (deduct from inventory when produced)
  - Availability checking with shortage reporting
  - Get available quantity (quantity - reserved)
- [x] Manufacturing order management (`app/services/production.py` - 250+ lines)
  - Create manufacturing orders with validation
  - Release orders to production (with full material validation)
  - Cancel orders (with material unreservation)
  - Get material requirements with BOM details
- [x] Manufacturing order API endpoints (5 endpoints fully functional)
  - GET /api/manufacturing-orders - list all with BOM details
  - POST /api/manufacturing-orders - create new order
  - GET /api/manufacturing-orders/{id} - get order with full BOM
  - PUT /api/manufacturing-orders/{id}/release - release to production
  - PUT /api/manufacturing-orders/{id}/cancel - cancel order
- [x] Purchasing service (`app/services/purchasing.py` - 290+ lines)
  - Issue purchase orders with wallet & capacity validation
  - Supplier catalog retrieval with daily price fluctuation
  - Material pricing lookup
  - Purchase order listing and tracking
- [x] Purchase order API endpoints (5 endpoints fully functional)
  - GET /api/suppliers - list all suppliers
  - GET /api/suppliers/{id}/catalog - supplier catalog with current pricing
  - GET /api/suppliers/{id}/pricing/{material_id} - specific material pricing
  - GET /api/purchase-orders - list all purchase orders
  - POST /api/purchase-orders - create new purchase order
- [x] POST /api/game/advance-day - full day advancement endpoint (atomic, transactional)
- [x] Event logging infrastructure (integrated into all state changes)
- [x] Full Pydantic schemas for manufacturing, purchasing, inventory responses

#### Testing ✅
- [x] Manufacturing order creation, release, and cancellation
- [x] Purchase order creation and pricing
- [x] Day advancement with demand generation, production, and fulfillment
- [x] Material reservation and consumption working correctly
- [x] API endpoints tested and validated
- [x] Full integration of simulation core with services

---

### Phase 3: Business Rules ⏳ NEXT

#### Planned
- Wallet constraint enforcement
- Warehouse capacity validation
- Production capacity limiting
- Material reservation system (DONE - integrated in Phase 2)
- Partial order handling
- Late delivery penalties
- Game over conditions (partially done)

---

*Last Updated: 2026-04-14*
*Current Milestone: Phase 2 Complete → Phase 3 Business Rules Enforcement*

---

*Last Updated: 2026-04-14*
*Current Milestone: Phase 1 Complete → Phase 2 Core Simulation In Progress*
