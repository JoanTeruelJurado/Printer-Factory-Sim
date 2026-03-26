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

### Phase 1: Foundation

#### Completed
- [x] PRD document created
- [x] CLAUDE.md initialized

#### In Progress
- [ ] Database schema implementation (`app/db/models.py`)
- [ ] Initial data seeding script

#### Next Steps
1. Set up project structure (directories, virtual environment)
2. Install dependencies (FastAPI, SQLAlchemy, Pydantic, etc.)
3. Implement SQLite models matching PRD schema
4. Create seed data (products, BOMs, suppliers, initial inventory)
5. Implement basic FastAPI app with health check endpoint
6. Test: Verify database creation and seed data load

#### Pending
- [ ] Simulation core
- [ ] Business rule services
- [ ] API endpoints
- [ ] Frontend UI
- [ ] Testing suite
- [ ] Documentation

---

*Last Updated: 2026-03-26*
*Current Milestone: Phase 1 - Foundation Setup*
