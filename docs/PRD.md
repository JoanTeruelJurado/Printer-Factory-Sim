# 3D Printer Factory Simulator - Product Requirements Document (PRD)

## 1. Executive Summary

### 1.1 Objective
Build a discrete-event simulation system that models the full production cycle of a factory manufacturing 3D printers. The user acts as production planner, making decisions about what to manufacture and what materials to purchase while managing inventory, costs, and production capacity.

### 1.2 Core Gameplay Loop
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Advance   │───▶│  New Orders  │───▶│   User      │
│    Day      │    │  Generated   │    │  Decisions  │
└─────────────┘    └──────────────┘    └─────────────┘
       ▲                                      │
       │                                      ▼
       │    ┌──────────────┐    ┌─────────────┐
       └────│ Events       │◀───│  Simulation │
            │ Logged       │    │  Processed  │
            └──────────────┘    └─────────────┘
```

### 1.3 Success Criteria
- Fully functional web-based simulator accessible from any browser
- Complete REST API with automatic OpenAPI documentation
- Import/export capability for game state
- Game enforcement: wallet cannot go negative, warehouse has capacity limits

---

## 2. Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Language** | Python 3.11+ | Readability, extensive libraries, cross-platform |
| **Backend Framework** | FastAPI | Async support, automatic OpenAPI docs, Pydantic validation |
| **Simulation Engine** | Custom discrete-event loop | Turn-based day progression matches gameplay needs better than SimPy's continuous event queue |
| **Database** | SQLite | ACID compliance, concurrent access, easy backup/export |
| **Frontend** | Vanilla HTML/CSS/JavaScript | No build tools required, full control over UX, minimal dependencies |
| **Charts** | matplotlib + base64 embedding | Streamlit-like chart generation compatible with FastAPI |
| **Serialization** | JSON | Human-readable export format |
| **Version Control** | Git + GitHub | Standard workflow |

### 2.1 Why Custom Simulation Over SimPy?
While SimPy is excellent for continuous simulation, our turn-based "Advance Day" mechanic maps more naturally to a simplified custom event loop:
- Day boundaries are explicit game mechanics, not just observation points
- User decisions happen at specific points in the day (after demand generation, before processing)
- Easier to explain and debug for educational purposes

---

## 3. Data Model

### 3.1 Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    Client    │       │  DemandOrder │       │  Manufacturer│
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │───┐   │ id (PK)      │       │ id (PK)      │
│ name         │   └──▶│ client_id(FK)│       │ name         │
└──────────────┘       │ product_id(FK)│      └──────────────┘
                       │ quantity     │              │
                       │ due_date     │              │ consumes
                       │ status       │              │
                       │ penalty_amt  │              │
                       │ created_day  │              │
                       └──────────────┘              │
                            │                        │
                            │ produces               │
                            ▼                        ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    Product   │◀──────│     BOM      │───────│RawMaterial   │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │       │ id (PK)      │       │ id (PK)      │
│ name         │       │ product_id   │       │ name         │
│ type         │       │ material_id  │       │ base_price   │
│ status       │       │ qty_needed   │       └──────────────┘
│ sell_price   │       └──────────────┘              │
└──────────────┘                                      │
         │                                            │
         │ sells to                                   │ sourced from
         ▼                                            ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Customer   │       │  Supplier    │       │ PurchaseOrd  │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │       │ id (PK)      │       │ id (PK)      │
│ name         │       │ name         │       │ supplier_id  │
│ contact      │       │ products[]   │       │ material_id  │
└──────────────┘       │ lead_time    │       │ quantity     │
                       │ min_qty      │       │ issue_day    │
                       └──────────────┘       │ expected_day │
                           │                  │ status       │
                           │ delivers         │ total_cost   │
                           ▼                  └──────────────┘
                    ┌──────────────┐                   │
                    │  Inventory   │◀──────────────────┘
                    ├──────────────┤
                    │ product_id   │
                    │ quantity     │
                    └──────────────┘
```

### 3.2 Schema Definitions (SQLite)

#### Products Table
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    product_type TEXT NOT NULL CHECK(product_type IN ('raw', 'finished')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'discontinued')),
    sell_price REAL,  -- NULL for raw materials
    assembly_time_hours REAL NOT NULL DEFAULT 0  -- For finished products only
);
```

#### RawMaterials Table
```sql
CREATE TABLE raw_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    base_price REAL NOT NULL,  -- Base price per unit
    volume_per_unit REAL NOT NULL DEFAULT 1  -- Storage volume units
);
```

#### Clients Table
```sql
CREATE TABLE clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
```

#### BillOfMaterials (BOM) Table
```sql
CREATE TABLE bom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    qty_needed REAL NOT NULL CHECK(qty_needed > 0),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (material_id) REFERENCES raw_materials(id),
    UNIQUE(product_id, material_id)
);
```

#### Suppliers Table
```sql
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    lead_time_days INTEGER NOT NULL CHECK(lead_time_days >= 0),
    reliability REAL NOT NULL DEFAULT 1.0 CHECK(reliability BETWEEN 0 AND 1)  -- Delay probability factor
);
```

#### SupplierProducts Table (Catalog with pricing tiers)
```sql
CREATE TABLE supplier_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    base_unit_cost REAL NOT NULL,  -- Base cost per unit
    daily_price_factor REAL NOT NULL DEFAULT 1.0,  -- Random fluctuation multiplier
    packaging_options TEXT NOT NULL DEFAULT '{"unit": 1, "box": 20, "pallet": 1000}',  -- JSON
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (material_id) REFERENCES raw_materials(id),
    UNIQUE(supplier_id, material_id)
);
```

#### Inventory Table
```sql
CREATE TABLE inventory (
    material_id INTEGER PRIMARY KEY,
    quantity REAL NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    reserved_quantity REAL NOT NULL DEFAULT 0 CHECK(reserved_quantity >= 0),
    FOREIGN KEY (material_id) REFERENCES raw_materials(id)
);
```

#### ManufacturingOrders Table
```sql
CREATE TABLE manufacturing_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    created_day INTEGER NOT NULL,
    release_day INTEGER,  -- NULL if not yet released
    completed_day INTEGER,  -- NULL if not completed
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'released', 'completed', 'cancelled')),
    remaining_qty INTEGER NOT NULL DEFAULT 0,  -- For partial completion tracking
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### DemandOrders Table (Sales orders from clients)
```sql
CREATE TABLE demand_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    request_day INTEGER NOT NULL,
    due_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'fulfilled', 'partial', 'lost')),
    fulfilled_qty INTEGER NOT NULL DEFAULT 0,
    penalty_amount REAL NOT NULL DEFAULT 0,  -- Applied if lost/partial
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### PurchaseOrders Table
```sql
CREATE TABLE purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    packaging_type TEXT NOT NULL,  -- 'unit', 'box', or 'pallet'
    issue_day INTEGER NOT NULL,
    expected_delivery_day INTEGER NOT NULL,
    actual_delivery_day INTEGER,  -- NULL until delivered
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'delivered', 'delayed', 'cancelled')),
    unit_cost REAL NOT NULL,  -- Cost per unit at time of order
    total_cost REAL NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (material_id) REFERENCES raw_materials(id)
);
```

#### DailyCosts Table (Configuration for operational expenses)
```sql
CREATE TABLE daily_costs (
    id INTEGER PRIMARY KEY CHECK(id = 1),  -- Singleton
    fixed_cost REAL NOT NULL DEFAULT 0,  -- Rent, salaries, etc.
    variable_cost_per_unit REAL NOT NULL DEFAULT 0,  -- Per printer produced
    energy_cost_per_hour REAL NOT NULL DEFAULT 0,  -- Per assembly hour
    maintenance_percentage REAL NOT NULL DEFAULT 0  -- Percentage of total costs
);
```

#### GameState Table
```sql
CREATE TABLE game_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),  -- Singleton
    current_day INTEGER NOT NULL DEFAULT 1,
    wallet_balance REAL NOT NULL DEFAULT 10000.0,
    warehouse_capacity INTEGER NOT NULL DEFAULT 10000,
    daily_production_capacity INTEGER NOT NULL DEFAULT 10,
    days_with_negative_balance INTEGER NOT NULL DEFAULT 0,
    game_over BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### Events Table (Audit log)
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    sim_day INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    details TEXT NOT NULL,  -- JSON blob with event-specific data
    category TEXT NOT NULL DEFAULT 'general' CHECK(category IN ('production', 'purchase', 'demand', 'inventory', 'financial', 'system', 'alert'))
);
CREATE INDEX idx_events_day ON events(sim_day);
CREATE INDEX idx_events_type ON events(event_type);
```

#### Configuration Table
```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,  -- JSON value
    description TEXT
);
```

---

## 4. Functional Requirements

### R0 — Initial Configuration

#### R0.1 Bill of Materials (BOM)
Define material requirements for each printer model:
- Each finished product has a BOM listing required raw materials and quantities
- BOM is editable via API/UI

#### R0.2 Assembly Time
- Each product has an assembly time in hours
- Determines production throughput within daily capacity

#### R0.3 Supplier Catalog
- Products for sale with prices by packaging tier (unit/box/pallet)
- Lead time configuration per supplier
- Daily price fluctuation (±10% random variation)

#### R0.4 Warehouse Capacity
- Configurable maximum storage volume
- Each raw material unit occupies 1 volume unit (simplified model)
- UI warning when approaching capacity (>80%)

### R1 — Demand Generation

#### R1.1 Daily Order Creation
At start of each simulated day:
- Generate 0-N demand orders based on configurable distribution
- Mean and variance parameters configurable globally or per-product
- Due dates randomly assigned (typically 3-7 days from creation)

#### R1.2 Configuration Parameters
```json
{
    "demand_generation": {
        "orders_per_day_mean": 3,
        "orders_per_day_variance": 2,
        "due_date_min_days": 3,
        "due_date_max_days": 7,
        "product_selection_mode": "weighted_random",
        "product_weights": {"printer_A": 0.5, "printer_B": 0.3, "printer_C": 0.2}
    }
}
```

### R2 — Control Dashboard

Display real-time information:
- **Current simulated day** and game status
- **Pending manufacturing orders** with BOM breakdown
- **Inventory levels** with shortage indicators
- **Open demand orders** with deadline countdown
- **Wallet balance** with alert thresholds

### R3 — User Decisions

#### R3.1 Release Production Orders
- Select pending manufacturing orders to release
- Must specify quantity ≤ daily remaining capacity
- Orders can be partially released (remaining quantity stays pending)
- Material reservation occurs upon release

#### R3.2 Issue Purchase Orders
- Select supplier and material
- Choose packaging tier (affects quantity and price)
- System validates:
  - Wallet can cover cost (no overdraft allowed)
  - Warehouse has available capacity
- Order issued immediately, delivery scheduled per lead time

#### R3.3 Cancel Orders
- Cancel unreleased manufacturing orders (no penalty)
- Cancel pending purchase orders (may have cancellation fee configured)

### R4 — Event Simulation

#### R4.1 Production Processing
During daily simulation cycle:
1. Check released orders have materials reserved
2. Consume materials according to BOM
3. Produce finished goods up to daily capacity
4. Update order status (completed/partially completed)

#### R4.2 Purchase Arrivals
- Calculate expected deliveries based on issue_day + lead_time
- Apply reliability factor for potential delays
- Add received quantities to inventory
- Deduct payment from wallet

#### R4.3 Daily Operational Costs
```
Daily Total = Fixed Cost + (Units Produced × Variable Cost) + (Assembly Hours × Energy Cost) × (1 + Maintenance %)
```

#### R4.4 Demand Fulfillment
At end of each day:
- Check completed orders against open demand orders
- Match supply to demand (FIFO by demand creation date)
- Mark demand as fulfilled/partial/lost
- Apply penalties for missed deliveries

### R5 — Calendar Advance

#### R5.1 Advance Day Button
Triggers complete 24h simulation cycle:
1. Increment day counter
2. Generate new demand orders
3. Process pending purchase deliveries
4. Process production (up to capacity)
5. Fulfill demand orders
6. Calculate and deduct daily costs
7. Log all events
8. Check game-over conditions

### R6 — Event Log

#### R6.1 Comprehensive Logging
All actions and automated events recorded with:
- Event type and category
- Simulated day
- Detailed JSON payload
- Categories: production, purchase, demand, inventory, financial, system, alert

#### R6.2 Queryable History
- Filter by type, date range, category
- Export for analysis/charts

### R7 — JSON Import/Export

#### R7.1 Full State Export
Export complete game state including:
- Current day and wallet balance
- All inventory levels
- All orders (manufacturing, demand, purchase)
- Event history
- Configuration

#### R7.2 Save/Load Games
- Save to JSON file
- Load from previously exported JSON
- Validation on load to ensure data integrity

### R8 — REST API

#### R8.1 Complete API Coverage
Every UI feature accessible via REST API:
- All CRUD operations
- All simulation triggers
- All query endpoints
- Automatic Swagger/OpenAPI documentation at `/docs`

### R9 — Cost/Benefits Simulator

#### R9.1 Wallet Management
- Starting balance: €10,000 (configurable)
- Income from fulfilled demand orders
- Expenses: materials, daily operational costs
- **Game ends if wallet goes negative**

#### R9.2 Warning System
- Warning at <€2,000 (configurable threshold)
- Critical warning at <€500
- Prevent purchase orders that would cause overdraft

#### R9.3 Daily Operational Costs (R9.4 from user answers)
Configurable parameters:
- Fixed daily cost (rent, salaries): €500/day default
- Variable cost per printer: €50/unit default
- Energy cost per assembly hour: €10/hour default
- Maintenance percentage: 5% default

### R10 — Stock Control

#### R10.1 Capacity Enforcement
- Warehouse capacity limit enforced
- Purchase orders blocked if insufficient space
- UI indicator showing capacity utilization

#### R10.2 Volume Calculation
- Each material unit = 1 volume unit (simplified)
- Reserved quantities count toward capacity
- Alert at >80% capacity utilization

---

## 5. API Endpoints

### 5.1 Game State & Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/game/state` | Get current game state (day, wallet, capacities) |
| POST | `/api/game/advance-day` | Trigger advance day simulation cycle |
| POST | `/api/game/reset` | Reset game to initial state |
| GET | `/api/game/stats` | Game statistics (produced, sold, revenue, etc.) |

### 5.2 Products & BOM

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products` | List all products (finished + raw) |
| POST | `/api/products` | Create new product |
| GET | `/api/products/{id}` | Get product details |
| PUT | `/api/products/{id}` | Update product |
| DELETE | `/api/products/{id}` | Delete product (if no dependents) |
| GET | `/api/products/{id}/bom` | Get BOM for a product |
| PUT | `/api/products/{id}/bom` | Update BOM for a product |

### 5.3 Inventory

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory` | Get all inventory levels |
| GET | `/api/inventory/material/{id}` | Get specific material inventory |
| GET | `/api/inventory/capacity` | Get capacity usage info |
| POST | `/api/inventory/adjust` | Manual adjustment (admin/debug) |

### 5.4 Demand Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/demand-orders` | List all demand orders (filterable) |
| GET | `/api/demand-orders/open` | Get open demand orders only |
| GET | `/api/demand-orders/{id}` | Get single demand order details |
| POST | `/api/demand-orders/{id}/fulfill` | Manually fulfill demand order |

### 5.5 Manufacturing Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/manufacturing-orders` | List all manufacturing orders |
| POST | `/api/manufacturing-orders` | Create new manufacturing order |
| GET | `/api/manufacturing-orders/{id}` | Get order details with BOM |
| PUT | `/api/manufacturing-orders/{id}/release` | Release order to production |
| PUT | `/api/manufacturing-orders/{id}/cancel` | Cancel order |
| GET | `/api/manufacturing-orders/{id}/requirements` | Calculate material requirements |

### 5.6 Suppliers & Purchasing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/suppliers` | List all suppliers |
| GET | `/api/suppliers/{id}` | Get supplier details |
| GET | `/api/suppliers/{id}/catalog` | Get supplier product catalog with current prices |
| GET | `/api/suppliers/{id}/pricing/{material_id}` | Get pricing for specific material |
| GET | `/api/purchase-orders` | List all purchase orders |
| POST | `/api/purchase-orders` | Issue new purchase order |
| GET | `/api/purchase-orders/{id}` | Get purchase order details |
| PUT | `/api/purchase-orders/{id}/cancel` | Cancel purchase order |

### 5.7 Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/clients` | List all clients |
| GET | `/api/clients/{id}` | Get client details |
| GET | `/api/clients/{id}/history` | Get client order history |

### 5.8 Events & Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List events (filterable by type, day, category) |
| GET | `/api/events/today` | Get today's events |
| GET | `/api/events/export` | Export events as JSON/CSV |

### 5.9 Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get all configuration |
| GET | `/api/config/{key}` | Get specific config value |
| PUT | `/api/config/{key}` | Update configuration |
| GET | `/api/config/daily-costs` | Get daily costs configuration |
| PUT | `/api/config/daily-costs` | Update daily costs |

### 5.10 Import/Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/full-state` | Export complete game state |
| POST | `/api/import/full-state` | Import game state from JSON |

---

## 6. API Response Examples

### 6.1 Game State
```json
{
    "current_day": 5,
    "wallet_balance": 8543.50,
    "warehouse_capacity": 10000,
    "warehouse_used": 4523,
    "daily_production_capacity": 10,
    "production_used_today": 3,
    "game_over": false,
    "warning_level": null
}
```

### 6.2 Manufacturing Order with BOM
```json
{
    "id": 42,
    "product_id": 1,
    "product_name": "Prosumer Printer X1",
    "quantity": 10,
    "created_day": 3,
    "release_day": null,
    "status": "pending",
    "remaining_qty": 10,
    "bom": [
        {"material_id": 1, "material_name": "ABS Filament Spool", "qty_per_unit": 2, "total_required": 20},
        {"material_id": 2, "material_name": "Aluminum Extrusion 1m", "qty_per_unit": 4, "total_required": 40},
        {"material_id": 3, "material_name": "Stepper Motor NEMA17", "qty_per_unit": 3, "total_required": 30}
    ],
    "material_availability": {
        "fully_available": false,
        "shortages": [{"material_id": 3, "available": 25, "required": 30, "shortage": 5}]
    }
}
```

### 6.3 Supplier Pricing
```json
{
    "supplier_id": 1,
    "supplier_name": "Industrial Materials Co.",
    "material_id": 5,
    "material_name": "PLA Filament",
    "base_price": 85.00,
    "daily_fluctuation": 1.05,
    "current_price_per_unit": 89.25,
    "packaging_options": [
        {"type": "unit", "quantity": 1, "price_per_unit": 89.25, "total": 89.25},
        {"type": "box", "quantity": 20, "price_per_unit": 80.33, "discount": 0.10, "total": 1606.50},
        {"type": "pallet", "quantity": 1000, "price_per_unit": 71.40, "discount": 0.20, "total": 71400.00}
    ],
    "lead_time_days": 3,
    "stock_status": "in_stock"
}
```

---

## 7. Frontend Architecture

### 7.1 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Day 5 │ Wallet: €8,543.50 │ Capacity: 3/10 used      │
│                 [Advance Day] [Export] [Import]                 │
├──────────────────┬──────────────────────────┬──────────────────┤
│ DEMAND ORDERS    │  PRODUCTION QUEUE        │  INVENTORY       │
│ ┌──────────────┐ │  ┌────────────────────┐  │  ┌────────────┐ │
│ │Due: Tomorrow │ │  │ Order #42: 10 units│  │  │ ABS: 245   │ │
│ │Printer X1 x5 │ │  │ [Release 5] [×]   │  │  │ Aluminum:  │ │
│ │[View BOM]    │ │  │ Order #43: 3 units │  │  │ 1,230      │ │
│ └──────────────┘ │  │ [Release 3] [×]   │  │  │ Motors: 87 │ │
├──────────────────┤  └────────────────────┘  ├──────────────────┤
│ PURCHASING                               │  DAILY SUMMARY      │
│ ┌──────────────────────────────────────┐ │  ┌──────────────┐  │
│ │ Supplier: [Industrial Materials ▼]  │ │  │ Produced: 5  │  │
│ │ Material: [PLA Filament ▼]          │ │  │ Pending: 13  │  │
│ │ Qty: [Pallet (1000) @ €71.40]       │ │  │ Revenue: €2k │  │
│ │ Total: €71,400.00                    │ │  │ Cost: €850   │  │
│ │ Available Space: 5,477 / 10,000     │ │  │ Net: +€1,150 │  │
│ │ [Issue Purchase Order]               │ │  └──────────────┘  │
│ └──────────────────────────────────────┘ │                     │
├──────────────────────────────────────────┴──────────────────────┤
│ EVENT LOG (Last 20)                                             │
│ Day 5 | Demand generated: 3 orders                              │
│ Day 5 | Purchase PO-042 delivered: 1000 PLA                    │
│ Day 4 | Order #40 completed: 8 Printers                        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Technical Implementation
- Single-page application using vanilla JavaScript
- Fetch API for REST calls
- Modal dialogs for complex actions (purchase order creation)
- Charts rendered as PNG via matplotlib (embedded as base64)
- Auto-refresh every 30 seconds (or WebSocket for future enhancement)

### 7.3 Key Pages/Views
1. **Dashboard** (main view with panels above)
2. **Orders Detail** (modal with full BOM breakdown)
3. **Supplier Catalog** (compare prices across suppliers)
4. **Event Log Browser** (full history with filters)
5. **Configuration** (admin settings)
6. **Reports & Analytics** (charts, KPIs)

---

## 8. Development Plan

### Phase 1: Foundation (Week 1)
**Goal:** Working skeleton with basic simulation loop

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 1.1 | DB-1 | Design and implement SQLite schema | 4h |
| 1.2 | BE-1 | Set up FastAPI project structure | 2h |
| 1.3 | BE-2 | Implement base models with Pydantic | 4h |
| 1.4 | SIM-1 | Create simulation engine core (day advancement) | 6h |
| 1.5 | API-1 | Implement game state endpoints | 4h |
| 1.6 | SEED-1 | Create initial data (products, BOM, suppliers) | 4h |

**Milestone 1:** Can advance days with empty/no-op simulation

### Phase 2: Core Simulation (Week 1-2)
**Goal:** Complete production and purchasing flow

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 2.1 | SIM-2 | Implement demand generation | 4h |
| 2.2 | SIM-3 | Implement production processing | 6h |
| 2.3 | SIM-4 | Implement purchase order flow | 6h |
| 2.4 | SIM-5 | Implement demand fulfillment logic | 4h |
| 2.5 | SIM-6 | Implement daily cost calculation | 4h |
| 2.6 | API-2 | Manufacturing orders endpoints | 6h |
| 2.7 | API-3 | Purchase orders endpoints | 6h |
| 2.8 | API-4 | Inventory endpoints | 4h |

**Milestone 2:** Full simulation loop working via API

### Phase 3: Business Rules (Week 2)
**Goal:** Enforce constraints and game rules

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 3.1 | BR-1 | Wallet management with overdraft prevention | 4h |
| 3.2 | BR-2 | Warehouse capacity enforcement | 4h |
| 3.3 | BR-3 | Production capacity limiting | 3h |
| 3.4 | BR-4 | Partial order release logic | 4h |
| 3.5 | BR-5 | Penalty calculation for lost sales | 3h |
| 3.6 | BR-6 | Game over conditions | 2h |

**Milestone 3:** All business rules enforced correctly

### Phase 4: Event System (Week 2)
**Goal:** Comprehensive logging and history

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 4.1 | EVT-1 | Event logging infrastructure | 4h |
| 4.2 | EVT-2 | Log all simulation events | 6h |
| 4.3 | API-5 | Events query endpoints | 4h |
| 4.4 | IMP-EXP-1 | JSON export functionality | 4h |
| 4.5 | IMP-EXP-2 | JSON import functionality | 4h |

**Milestone 4:** Complete audit trail and save/load

### Phase 5: Frontend (Week 3)
**Goal:** Usable web interface

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 5.1 | FE-1 | Basic HTML layout with CSS | 6h |
| 5.2 | FE-2 | Dashboard panel components | 8h |
| 5.3 | FE-3 | Order management interface | 6h |
| 5.4 | FE-4 | Purchasing interface | 6h |
| 5.5 | FE-5 | Chart integration (matplotlib→PNG) | 4h |
| 5.6 | FE-6 | Modal dialogs for actions | 4h |
| 5.7 | FE-7 | Responsive design tweaks | 4h |

**Milestone 5:** Fully functional UI

### Phase 6: Polish & Documentation (Week 3)
**Goal:** Professional finish

| Task | ID | Description | Estimate |
|------|-----|-------------|----------|
| 6.1 | DOC-1 | Complete OpenAPI documentation | 4h |
| 6.2 | DOC-2 | README and setup instructions | 4h |
| 6.3 | DOC-3 | Code comments and docstrings | 6h |
| 6.4 | TEST-1 | Unit tests for simulation logic | 8h |
| 6.5 | TEST-2 | API endpoint tests | 6h |
| 6.6 | FIX-1 | Bug fixes and edge cases | 8h |
| 6.7 | PERF-1 | Performance optimization | 4h |

**Final Milestone:** Production-ready system

---

## 9. Timeline Summary

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1** | 3 days | Skeleton architecture, database, simulation core |
| **Phase 2** | 4 days | Complete simulation logic, all API endpoints |
| **Phase 3** | 2 days | Business rule enforcement |
| **Phase 4** | 2 days | Event logging, import/export |
| **Phase 5** | 4 days | Full frontend implementation |
| **Phase 6** | 4 days | Testing, documentation, polish |
| **Total** | **~19 working days** | ~3 weeks full-time |

### Buffer & Contingency (+20%)
- Unexpected complexity: +4 days
- Integration issues: +2 days
- **Adjusted estimate: ~25 working days (~5 weeks part-time)**

---

## 10. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| SimPy vs custom engine decision | Medium | Start with custom; can refactor if needed |
| Frontend complexity underestimated | High | Use simple patterns, avoid premature polish |
| SQLite performance at scale | Low-Medium | Expected data volume is small; add indexing |
| Price fluctuation logic too complex | Low | Start with simple ±10% uniform distribution |
| Partial order release edge cases | Medium | Thorough testing of boundary conditions |

---

## 11. Acceptance Criteria

### Minimum Viable Product (MVP)
- [ ] Can advance days and see simulation progress
- [ ] Demand orders are generated and trackable
- [ ] Can create and release manufacturing orders
- [ ] Materials are consumed according to BOM
- [ ] Can issue purchase orders through suppliers
- [ ] Wallet balance updates correctly
- [ ] Game enforces non-negative wallet constraint
- [ ] Game enforces warehouse capacity constraint
- [ ] All events are logged
- [ ] Can export/import game state as JSON
- [ ] All features accessible via REST API
- [ ] Swagger docs auto-generated and accurate

### Stretch Goals
- [ ] Email/dashboard notifications for low wallet
- [ ] Advanced analytics dashboard
- [ ] Multiple supplier comparison view
- [ ] Scenario planning mode
- [ ] Achievement/trophy system
- [ ] Multi-currency support

---

## 13. Week 7 — Retail Supply Chain & Agent Orchestration

### 13.1 Overview

Week 7 extends the two-app system (Provider + Manufacturer) into a full three-tier retail supply chain. A new Retailer application sits between end customers and the Manufacturer, placing production orders and selling finished printers to the public. An external Turn Engine orchestrates simulated days across all three apps in sequence. AI agent skills replace manual decision-making for each role.

### 13.2 Three-App Architecture

```
Provider :8001  (supplier.db)
    │  raw material orders
    ▼
Manufacturer :8002  (simulator.db)
    │  finished printer orders (SalesOrders)
    ▼
Retailer :8003  (retailer.db)
    │  retail sales
    ▼
End Customers
```

Each app has its own SQLite database and communicates with adjacent apps exclusively via REST. No shared database connections exist across app boundaries.

| App | Port | Database | Role |
|-----|------|----------|------|
| Provider | 8001 | supplier.db | Raw material supplier |
| Manufacturer | 8002 | simulator.db | Factory production |
| Retailer | 8003 | retailer.db | Retail sales |

### 13.3 Retailer Application (Port 8003)

#### 13.3.1 Catalog Management

The retailer sells two printer models sourced from the Manufacturer:

| SKU | Name | Description |
|-----|------|-------------|
| P3D-Classic | P3D-Classic | Entry-level 3D printer |
| P3D-Pro | P3D-Pro | Professional 3D printer |

Catalog entries store the retail sell price, the manufacturer product ID used when placing purchase orders, and current stock levels.

#### 13.3.2 Customer Order Handling

- Customer orders arrive as inbound requests specifying SKU and quantity.
- On receipt, the retailer attempts immediate fulfillment from available stock.
- If sufficient stock exists: order status set to `fulfilled`, stock decremented.
- If stock is insufficient: order status set to `backordered`, and a purchase order is automatically raised to the Manufacturer for the shortfall.
- Backorders are fulfilled automatically during day advancement when the corresponding Manufacturer delivery arrives.

#### 13.3.3 Purchase Orders to Manufacturer

- Retailer places purchase orders against the Manufacturer's sales order API (`POST /api/sales-orders`).
- Purchase order tracks: SKU, quantity, order day, expected delivery day, status (`pending` / `shipped` / `delivered`).
- Payment is deducted from the retailer wallet on order placement.
- Delivered stock is added to retailer inventory during the day-advance cycle.

#### 13.3.4 Stock Tracking

- Per-SKU stock levels tracked in `retailer.db`.
- Stock is decremented on customer fulfillment and incremented on Manufacturer delivery.
- Low-stock threshold configurable; alerts logged as events.

#### 13.3.5 Wallet Management

- Starting wallet: €50,000 (configurable on reset).
- Income: customer order payments on fulfillment.
- Expenses: purchase orders to Manufacturer, daily fixed operating costs.
- Wallet check enforced before placing purchase orders (no overdraft).

#### 13.3.6 Day Advancement

On `POST /api/day/advance`:
1. Process incoming Manufacturer deliveries → increment stock, fulfill backorders.
2. Apply daily fixed operating costs.
3. Log all events.
4. Increment current day.

#### 13.3.7 Retailer API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/state` | Retailer game state (day, wallet, stock) |
| GET | `/api/catalog` | List all SKUs with stock and pricing |
| POST | `/api/orders` | Place a customer order |
| GET | `/api/orders` | List customer orders (optional `?status=`) |
| GET | `/api/orders/{id}` | Customer order detail |
| POST | `/api/purchase-orders` | Place purchase order to Manufacturer |
| GET | `/api/purchase-orders` | List all purchase orders |
| POST | `/api/day/advance` | Advance retailer day |
| GET | `/api/export` | Export retailer state as JSON |
| POST | `/api/import` | Restore retailer state from JSON |
| POST | `/api/reset` | Reset retailer to day 1 |
| GET | `/api/agent/context` | Full state snapshot for AI agents |

### 13.4 Sales Orders (Manufacturer)

Sales orders replace the stochastic demand order system for inter-app flow. Instead of random demand generation, the Manufacturer receives explicit orders from the Retailer via the sales order API.

#### 13.4.1 SalesOrder Model

```
SalesOrder
  id              INTEGER PK
  retailer_id     INTEGER           -- identifies the requesting retailer
  product_id      INTEGER FK → products
  quantity        INTEGER
  created_day     INTEGER
  due_day         INTEGER
  status          TEXT              -- pending | released | completed | shipped | delivered
  fulfilled_qty   INTEGER DEFAULT 0
  unit_price      REAL              -- agreed price at order time
  total_value     REAL
```

#### 13.4.2 Status Lifecycle

```
pending
   │  (MO created and released)
   ▼
released
   │  (production completes in advance_day)
   ▼
completed
   │  (Manufacturer ships to Retailer)
   ▼
shipped
   │  (Retailer advances day and receives delivery)
   ▼
delivered
```

- Materials are reserved against inventory when the sales order transitions to `released`.
- Production is processed as part of the normal `advance_day` cycle alongside internal manufacturing orders.
- On completion, the Manufacturer marks the order `shipped` and notifies the Retailer (or the Turn Engine triggers the Retailer advance which polls for shipped orders).

#### 13.4.3 Manufacturer Sales Order API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sales-orders` | Create a new sales order from Retailer |
| GET | `/api/sales-orders` | List all sales orders (optional `?status=`) |
| GET | `/api/sales-orders/{id}` | Sales order detail |
| PUT | `/api/sales-orders/{id}/release` | Release to production (reserve materials) |
| PUT | `/api/sales-orders/{id}/ship` | Mark order as shipped |
| GET | `/api/sales-orders/due?day=N` | Orders completed and ready to ship |

### 13.5 Turn Engine Orchestration

The Turn Engine is an external Python script that drives one simulated calendar day across all three apps in a deterministic sequence. It decouples orchestration from application business logic.

#### 13.5.1 Invocation

```bash
python turn_engine.py config/sim.json scenarios/smoke-test.json 3
```

Arguments:
- `config/sim.json` — base configuration (app URLs, timeouts, log directory)
- `scenarios/smoke-test.json` — scenario definition (initial state, agent skill overrides, number of days)
- `3` — number of days to simulate in this run

#### 13.5.2 Day Cycle Sequence

For each simulated day the Turn Engine executes the following steps in order:

```
1. inject_demand(retailer)
      POST /api/orders  — inject customer orders per scenario demand profile

2. retailer_decisions(retailer)
      invoke agent skill: skills/retailer-manager.md
      agent reads GET /api/agent/context, decides purchase orders to Manufacturer

3. manufacturer_decisions(manufacturer)
      invoke agent skill: skills/manufacturer-manager.md
      agent reads GET /api/agent/context, decides MOs to release, POs to Provider

4. provider_decisions(provider)
      invoke agent skill: skills/provider-manager.md
      agent reads GET /api/catalog and /api/stock, adjusts pricing tiers or restock

5. advance_provider(provider)
      POST /api/day/advance  — ships pending orders, replenishes stock, increments day

6. advance_manufacturer(manufacturer)
      POST /api/game/advance-day  — fluctuates prices, processes deliveries, runs
                                     production, deducts costs, increments day

7. advance_retailer(retailer)
      POST /api/day/advance  — processes Manufacturer deliveries, fulfills
                                backorders, deducts costs, increments day

8. log_day_summary()
      write logs/day-NNN-summary.json with wallet balances and key metrics
```

#### 13.5.3 Configuration Files

`config/sim.json`:
```json
{
    "apps": {
        "provider":     { "url": "http://localhost:8001" },
        "manufacturer": { "url": "http://localhost:8002" },
        "retailer":     { "url": "http://localhost:8003" }
    },
    "agent_timeout_seconds": 180,
    "log_dir": "logs"
}
```

`scenarios/smoke-test.json`:
```json
{
    "name": "smoke-test",
    "days": 3,
    "daily_demand": [
        { "sku": "P3D-Classic", "quantity": 2 },
        { "sku": "P3D-Pro",     "quantity": 1 }
    ],
    "agent_skills": {
        "retailer":     "skills/retailer-manager.md",
        "manufacturer": "skills/manufacturer-manager.md",
        "provider":     null
    }
}
```

### 13.6 Agent Skill System

Each app role is driven by a Claude agent invoked via `claude --print`. Skill files are markdown documents that describe the decision framework for that role.

#### 13.6.1 Skill Invocation

The Turn Engine invokes an agent skill as:

```bash
claude --print "$(cat skills/manufacturer-manager.md)\n\n## Current Context\n$(curl -s http://localhost:8002/api/agent/context)"
```

- Timeout: 180 seconds per invocation.
- stdout is captured to `logs/day-NNN-<role>.log`.
- The agent is expected to emit a sequence of `curl` or structured API call commands that the Turn Engine parses and executes, or the agent calls the APIs directly using tool use if running in an agentic context.

#### 13.6.2 Skill Files

| File | Role | Responsibility |
|------|------|---------------|
| `skills/manufacturer-manager.md` | Manufacturer agent | Decide which MOs to release, which raw materials to purchase, based on open sales orders, inventory levels, wallet balance, and supplier pricing |
| `skills/retailer-manager.md` | Retailer agent | Decide how many units of each SKU to order from the Manufacturer based on current stock, pending customer backorders, and wallet balance |
| `skills/provider-manager.md` | Provider agent | Optionally adjust pricing tiers or trigger restocks; normally a no-op unless scenario overrides |

#### 13.6.3 manufacturer-manager.md Decision Framework

The manufacturer agent follows this logic on each turn:

1. Read `/api/agent/context` — open sales orders, inventory, wallet, BOM, supplier pricing.
2. For each open sales order: check if materials are available; if yes, release an MO.
3. For any material shortage: compute quantity needed across all pending sales orders; issue purchase orders using the best-priced supplier tier that fits within wallet constraints.
4. Prioritise orders with the nearest due day.
5. Do not over-commit wallet: leave a buffer of at least €1,000.

#### 13.6.4 Log Artifacts

Each day produces:
- `logs/day-NNN-retailer.log` — raw agent output for retailer decisions
- `logs/day-NNN-manufacturer.log` — raw agent output for manufacturer decisions
- `logs/day-NNN-provider.log` — raw agent output for provider decisions (if skill active)
- `logs/day-NNN-summary.json` — structured metrics snapshot

### 13.7 Week 7 Acceptance Criteria

- [ ] Retailer app starts on port 8003 with €50,000 starting wallet and P3D-Classic / P3D-Pro catalog
- [ ] Customer orders auto-fulfill from stock or backorder correctly
- [ ] Retailer purchase orders reach Manufacturer and create SalesOrders
- [ ] SalesOrder lifecycle transitions correctly: pending → released → completed → shipped → delivered
- [ ] Materials are reserved on SalesOrder release and consumed on production completion
- [ ] Turn Engine runs a 3-day smoke-test scenario end-to-end without errors
- [ ] All three apps advance in lockstep (same simulated day after each Turn Engine cycle)
- [ ] Agent skills produce valid API calls within the 180s timeout
- [ ] Day logs written to `logs/` for each simulated day
- [ ] All existing 98 tests continue to pass after Manufacturer changes

---

## 12. Appendix

### A. Example Initial Data

#### Products
| id | name | type | sell_price | assembly_time |
|----|------|------|------------|---------------|
| 1 | Hobby Printer Mini | finished | 350.00 | 2.0 |
| 2 | Prosumer Printer X1 | finished | 850.00 | 4.0 |
| 3 | Industrial Printer Pro | finished | 2500.00 | 8.0 |

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

#### BOM Example (Prosumer Printer X1)
| product_id | material_id | qty_per_unit |
|------------|-------------|--------------|
| 2 | 1 | 2 |
| 2 | 2 | 3 |
| 2 | 3 | 4 |
| 2 | 5 | 3 |
| 2 | 6 | 6 |
| 2 | 7 | 1 |
| 2 | 8 | 1 |

#### Suppliers
| id | name | lead_time_days | reliability |
|----|------|----------------|-------------|
| 1 | Industrial Materials Co. | 3 | 0.95 |
| 2 | QuickShip Components | 1 | 0.85 |
| 3 | Global Sourcing Ltd | 7 | 0.98 |

#### Default Configuration
```json
{
    "starting_wallet": 10000.00,
    "warehouse_capacity": 10000,
    "daily_production_capacity": 10,
    "daily_costs": {
        "fixed_cost": 500.00,
        "variable_cost_per_unit": 50.00,
        "energy_cost_per_hour": 10.00,
        "maintenance_percentage": 0.05
    },
    "demand_generation": {
        "orders_per_day_mean": 3,
        "orders_per_day_variance": 2
    },
    "price_fluctuation": {
        "daily_variation_percent": 0.10
    },
    "warnings": {
        "wallet_warning_threshold": 2000.00,
        "wallet_critical_threshold": 500.00,
        "capacity_warning_threshold": 0.80
    }
}
```

### B. Glossary

| Term | Definition |
|------|------------|
| BOM | Bill of Materials - list of raw materials needed to produce a finished product |
| Lead Time | Days between issuing a purchase order and receiving materials |
| Demand Order | Customer request for finished printers (sales order) |
| Manufacturing Order | Internal work order to produce finished goods |
| Purchase Order | Request to supplier for raw materials |
| Daily Capacity | Maximum number of printer units producible per day |

---

*Document Version: 1.0*
*Created: 2026-03-26*
*Status: Ready for Review*
