"""
Dashboard API: combined 3-app state and single-turn execution.

Provides two endpoints:
  GET  /state    — read-only snapshot of all three apps
  POST /run-turn — inject demand + advance all apps, return combined state
"""

import json
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    DemandOrder,
    GameState,
    Inventory,
    ManufacturerMetrics,
    ManufacturingOrder,
    Product,
    RawMaterial,
    SalesOrder,
)
from app.db.models import BOM
from app.services.inventory import check_material_availability
from app.services.production import (
    ProductionError,
    create_manufacturing_order,
    release_manufacturing_order,
)
from app.services.purchasing import PurchasingError, issue_purchase_order
from app.services.simulation import SimulationError, advance_day
from turn_engine.config import load_scenario, todays_signal
from turn_engine.engine import generate_customer_orders

router = APIRouter()

PROVIDER_URL = "http://localhost:8001"
RETAILER_URL = "http://localhost:8003"
_TIMEOUT = httpx.Timeout(10.0)

# Module-level scenario cache: {path: scenario_dict}
_scenario_cache: dict[str, dict] = {}


def _get_scenario(scenario_file: str) -> dict:
    """Load and cache a scenario file."""
    if scenario_file not in _scenario_cache:
        _scenario_cache[scenario_file] = load_scenario(scenario_file)
    return _scenario_cache[scenario_file]


def _fetch_retailer_state() -> dict:
    """GET /api/agent/context from the Retailer API."""
    try:
        resp = httpx.get(f"{RETAILER_URL}/api/agent/context", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return {}


def _fetch_provider_catalog() -> list[dict]:
    """GET /api/catalog from the Provider API."""
    try:
        resp = httpx.get(f"{PROVIDER_URL}/api/catalog", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return []


def _fetch_provider_stock() -> list[dict]:
    """GET /api/stock from the Provider API."""
    try:
        resp = httpx.get(f"{PROVIDER_URL}/api/stock", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return []


def _fetch_provider_orders() -> list[dict]:
    """GET /api/orders from the Provider API (pending orders)."""
    try:
        resp = httpx.get(
            f"{PROVIDER_URL}/api/orders",
            params={"status": "pending"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return []


def _fetch_provider_day() -> int:
    """GET /api/day/current from the Provider API."""
    try:
        resp = httpx.get(f"{PROVIDER_URL}/api/day/current", timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("current_day", data.get("day", 0))
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return 0


def _build_manufacturer_state(db: Session) -> dict:
    """Build manufacturer state dict from the local DB."""
    state = db.query(GameState).filter(GameState.id == 1).first()
    if not state:
        return {}

    # Parts stock
    parts_stock: dict[str, int] = {}
    for inv in db.query(Inventory).all():
        mat = db.query(RawMaterial).filter_by(id=inv.material_id).first()
        if mat:
            parts_stock[mat.name] = int(inv.quantity - inv.reserved_quantity)

    # Finished goods stock
    finished_stock: dict[str, int] = {}
    for prod in db.query(Product).filter_by(product_type="finished").all():
        completed_qty = sum(
            mo.quantity
            for mo in db.query(ManufacturingOrder)
            .filter_by(product_id=prod.id, status="completed")
            .all()
        )
        fulfilled_qty = sum(
            d.fulfilled_qty
            for d in db.query(DemandOrder)
            .filter(
                DemandOrder.product_id == prod.id,
                DemandOrder.status.in_(["fulfilled", "partial"]),
            )
            .all()
        )
        shipped_sales_qty = sum(
            so.quantity
            for so in db.query(SalesOrder)
            .filter(
                SalesOrder.product_id == prod.id,
                SalesOrder.status.in_(["shipped", "delivered"]),
            )
            .all()
        )
        finished_stock[prod.name] = max(
            0, completed_qty - fulfilled_qty - shipped_sales_qty
        )

    # Utilisation from latest metrics row (or 0)
    latest_metric = (
        db.query(ManufacturerMetrics)
        .order_by(ManufacturerMetrics.sim_day.desc())
        .first()
    )
    utilisation = latest_metric.production_utilisation if latest_metric else 0.0

    # Open demands
    open_demands = (
        db.query(DemandOrder)
        .filter(DemandOrder.status.in_(["open", "partial"]))
        .count()
    )

    # Active MOs
    active_mos = (
        db.query(ManufacturingOrder)
        .filter(ManufacturingOrder.status.in_(["pending", "released"]))
        .count()
    )

    return {
        "day": state.current_day,
        "wallet": state.wallet_balance,
        "parts_stock": parts_stock,
        "finished_stock": finished_stock,
        "utilisation": round(utilisation, 3),
        "production_capacity": state.daily_production_capacity,
        "open_demands": open_demands,
        "active_mos": active_mos,
    }


def _build_retailer_state(ctx: dict) -> dict:
    """Transform retailer agent context into dashboard shape.

    The retailer /api/agent/context returns:
      game: {current_day, wallet}
      catalog: [{model_name, retail_price, wholesale_price, stock_on_hand}, ...]
      open_orders: [...]
      stats: {recent_fulfilled_5d, recent_backordered_5d, pending_orders, backordered_orders}
    """
    if not ctx:
        return {}

    game = ctx.get("game", {})
    catalog_list = ctx.get("catalog", [])
    stats = ctx.get("stats", {})

    stock: dict[str, int] = {}
    prices: dict[str, float] = {}
    for item in catalog_list:
        name = item.get("model_name", "")
        stock[name] = item.get("stock_on_hand", 0)
        prices[name] = item.get("retail_price", 0.0)

    return {
        "day": game.get("current_day", 0),
        "wallet": game.get("wallet", 0.0),
        "stock": stock,
        "prices": prices,
        "open_orders": stats.get("pending_orders", 0),
        "fulfilled_orders": stats.get("recent_fulfilled_5d", 0),
        "backordered": stats.get("backordered_orders", 0),
    }


def _build_provider_state(
    catalog: list[dict], stock: list[dict], pending_orders: list[dict], day: int
) -> dict:
    """Build provider state from catalog/stock/orders responses."""
    stock_map: dict[str, int] = {}
    for item in stock:
        name = item.get("product_name", item.get("material_name", str(item.get("id", ""))))
        qty = item.get("quantity", item.get("stock", 0))
        stock_map[name] = stock_map.get(name, 0) + int(qty)

    price_map: dict[str, float] = {}
    items = catalog if isinstance(catalog, list) else []
    for item in items:
        name = item.get("product_name", item.get("material_name", ""))
        price = item.get("effective_price", item.get("base_unit_cost", 0.0))
        if name:
            price_map[name] = round(price, 2)

    return {
        "day": day,
        "stock": stock_map,
        "prices": price_map,
        "pending_orders": len(pending_orders),
    }


def _build_metrics_history(db: Session) -> list[dict]:
    """Read last 30 days of metrics from ManufacturerMetrics."""
    rows = (
        db.query(ManufacturerMetrics)
        .order_by(ManufacturerMetrics.sim_day.desc())
        .limit(30)
        .all()
    )
    rows.reverse()  # chronological order

    # Fetch retailer metrics via HTTP
    retailer_metrics: dict[int, dict] = {}
    try:
        resp = httpx.get(f"{RETAILER_URL}/api/metrics", timeout=_TIMEOUT)
        if resp.status_code == 200:
            for m in resp.json():
                retailer_metrics[m.get("sim_day", 0)] = m
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        pass

    history: list[dict] = []
    for row in rows:
        parts = json.loads(row.parts_stock_json) if row.parts_stock_json else {}
        finished = json.loads(row.finished_stock_json) if row.finished_stock_json else {}
        total_parts = sum(parts.values())
        total_finished = sum(finished.values())

        ret = retailer_metrics.get(row.sim_day, {})
        ret_stock_json = ret.get("printer_stock_json")
        ret_total_stock = 0
        if ret_stock_json:
            try:
                ret_total_stock = sum(json.loads(ret_stock_json).values())
            except (json.JSONDecodeError, AttributeError):
                pass

        history.append({
            "day": row.sim_day,
            "mfg_wallet": round(row.wallet_balance, 2),
            "ret_wallet": ret.get("wallet_balance", 0.0),
            "parts_stock": total_parts,
            "finished_stock": total_finished,
            "ret_stock": ret_total_stock,
            "produced": round(row.production_utilisation * 10, 1),  # approx
            "fulfilled": ret.get("customer_orders_fulfilled", 0),
            "backordered": ret.get("customer_orders_backordered", 0),
        })

    return history


def _build_combined_state(
    db: Session,
    scenario_file: str | None = None,
    turn_result: dict | None = None,
) -> dict:
    """Assemble the full dashboard JSON response."""
    # Manufacturer (local DB)
    manufacturer = _build_manufacturer_state(db)
    current_day = manufacturer.get("day", 1)

    # Scenario / signal
    scenario_block: dict = {
        "name": None,
        "active_events": [],
        "demand_modifier": 1.0,
        "supply_modifier": 1.0,
        "lead_time_modifier": 1.0,
        "price_sensitivity": None,
    }
    if scenario_file:
        try:
            scenario = _get_scenario(scenario_file)
            signal = todays_signal(current_day, scenario)
            scenario_block = {
                "name": scenario.get("scenario_name"),
                "active_events": [
                    {"name": e.get("name", ""), "description": e.get("description", "")}
                    for e in signal.get("active_events", [])
                ],
                "demand_modifier": signal.get("demand_modifier", 1.0),
                "supply_modifier": signal.get("supply_modifier", 1.0),
                "lead_time_modifier": signal.get("lead_time_modifier", 1.0),
                "price_sensitivity": signal.get("price_sensitivity"),
            }
        except (FileNotFoundError, ValueError):
            pass

    # Retailer (HTTP)
    retailer_ctx = _fetch_retailer_state()
    retailer = _build_retailer_state(retailer_ctx)

    # Provider (HTTP)
    provider_catalog = _fetch_provider_catalog()
    provider_stock = _fetch_provider_stock()
    provider_orders = _fetch_provider_orders()
    provider_day = _fetch_provider_day()
    provider = _build_provider_state(
        provider_catalog, provider_stock, provider_orders, provider_day
    )

    # Turn block
    turn: dict = {
        "day": current_day,
        "demands_injected": 0,
        "produced": 0,
        "deliveries": 0,
        "expired_demands": 0,
    }
    if turn_result:
        turn = {
            "day": turn_result.get("day", current_day),
            "demands_injected": turn_result.get("demands_injected", 0),
            "produced": turn_result.get("produced", 0),
            "deliveries": turn_result.get("deliveries", 0),
            "expired_demands": turn_result.get("expired_demands", 0),
            "autopilot": turn_result.get("autopilot"),
        }

    # Metrics history
    metrics_history = _build_metrics_history(db)

    return {
        "turn": turn,
        "scenario": scenario_block,
        "manufacturer": manufacturer,
        "retailer": retailer,
        "provider": provider,
        "metrics_history": metrics_history,
    }


@router.get("/state")
def get_combined_state(
    scenario_file: Optional[str] = Query(
        default=None,
        description="Path to scenario file for signal info (optional)",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Return combined 3-app state without advancing any simulation."""
    return _build_combined_state(db, scenario_file=scenario_file)


def _autopilot_manufacturer(db: Session, current_day: int) -> dict:
    """Simple autopilot: purchase materials, create MOs, fulfill demands.

    Returns a summary dict of actions taken.
    """
    actions: dict = {"materials_ordered": 0, "mos_created": 0, "mos_released": 0,
                     "demands_fulfilled": 0, "sales_fulfilled": 0}
    state = db.query(GameState).filter(GameState.id == 1).first()
    if not state:
        return actions

    # --- 1. Purchase materials if stock is low ---
    for inv in db.query(Inventory).all():
        available = inv.quantity - inv.reserved_quantity
        if available < 80 and state.wallet_balance > 1500:
            mat = db.query(RawMaterial).filter_by(id=inv.material_id).first()
            if not mat:
                continue
            qty = 30
            try:
                issue_purchase_order(db, supplier_id=1, material_id=mat.id,
                                     quantity=qty, current_day=current_day)
                actions["materials_ordered"] += 1
            except (PurchasingError, Exception):
                pass

    # --- 2. Create + release MOs for products with open demand ---
    products = db.query(Product).filter_by(product_type="finished").all()
    for prod in products:
        # Count open demands
        open_demand = sum(
            d.quantity - d.fulfilled_qty
            for d in db.query(DemandOrder).filter(
                DemandOrder.product_id == prod.id,
                DemandOrder.status.in_(["open", "partial"]),
            ).all()
        )
        # Count open sales orders
        open_sales = sum(
            so.quantity
            for so in db.query(SalesOrder).filter(
                SalesOrder.product_id == prod.id,
                SalesOrder.status.in_(["pending", "released"]),
            ).all()
        )
        # Count existing pending/released MOs
        active_mo_qty = sum(
            mo.remaining_qty
            for mo in db.query(ManufacturingOrder).filter(
                ManufacturingOrder.product_id == prod.id,
                ManufacturingOrder.status.in_(["pending", "released"]),
            ).all()
        )

        needed = max(0, open_demand + open_sales - active_mo_qty)
        if needed <= 0:
            # Also proactively build some stock
            needed = 2

        qty = min(needed, state.daily_production_capacity)
        if qty <= 0:
            continue

        try:
            mo = create_manufacturing_order(db, prod.id, qty, current_day)
            actions["mos_created"] += 1
            try:
                release_manufacturing_order(db, mo.id, qty)
                actions["mos_released"] += 1
            except ProductionError:
                pass  # not enough materials to release
        except ProductionError:
            pass

    # --- 3. Fulfill open demand orders from finished goods ---
    for demand in (
        db.query(DemandOrder)
        .filter(DemandOrder.status.in_(["open", "partial"]))
        .order_by(DemandOrder.due_day)
        .all()
    ):
        completed_qty = sum(
            mo.quantity for mo in db.query(ManufacturingOrder).filter_by(
                product_id=demand.product_id, status="completed"
            ).all()
        )
        used_qty = sum(
            d.fulfilled_qty for d in db.query(DemandOrder).filter(
                DemandOrder.product_id == demand.product_id,
                DemandOrder.status.in_(["fulfilled", "partial"]),
                DemandOrder.id != demand.id,
            ).all()
        )
        shipped_qty = sum(
            so.quantity for so in db.query(SalesOrder).filter(
                SalesOrder.product_id == demand.product_id,
                SalesOrder.status.in_(["shipped", "delivered"]),
            ).all()
        )
        available = max(0, completed_qty - used_qty - shipped_qty)
        needed = demand.quantity - demand.fulfilled_qty
        to_serve = min(needed, available)
        if to_serve > 0:
            demand.fulfilled_qty += to_serve
            on_time = current_day <= demand.due_day
            if on_time:
                revenue = to_serve * demand.product.sell_price
                state.wallet_balance += revenue
            if demand.fulfilled_qty >= demand.quantity:
                demand.status = "fulfilled"
            else:
                demand.status = "partial"
            actions["demands_fulfilled"] += 1

    # --- 4. Fulfill sales orders from finished goods ---
    for so in (
        db.query(SalesOrder)
        .filter(SalesOrder.status == "pending")
        .order_by(SalesOrder.id)
        .all()
    ):
        completed_qty = sum(
            mo.quantity for mo in db.query(ManufacturingOrder).filter_by(
                product_id=so.product_id, status="completed"
            ).all()
        )
        used_qty = sum(
            d.fulfilled_qty for d in db.query(DemandOrder).filter(
                DemandOrder.product_id == so.product_id,
                DemandOrder.status.in_(["fulfilled", "partial"]),
            ).all()
        )
        shipped_qty = sum(
            s.quantity for s in db.query(SalesOrder).filter(
                SalesOrder.product_id == so.product_id,
                SalesOrder.status.in_(["shipped", "delivered"]),
            ).all()
        )
        available = max(0, completed_qty - used_qty - shipped_qty)
        if available >= so.quantity:
            so.status = "shipped"
            actions["sales_fulfilled"] += 1

    db.flush()
    return actions


def _autopilot_retailer() -> dict:
    """Tell retailer to fulfill pending orders and restock from manufacturer."""
    actions: dict = {"fulfilled": 0, "purchases": 0}

    # Fulfill all pending orders
    try:
        resp = httpx.get(f"{RETAILER_URL}/api/orders", params={"status": "pending"},
                         timeout=_TIMEOUT)
        if resp.status_code == 200:
            orders = resp.json().get("orders", [])
            for order in orders:
                try:
                    r = httpx.post(f"{RETAILER_URL}/api/orders/{order['id']}/fulfill",
                                   timeout=_TIMEOUT)
                    if r.status_code == 200:
                        actions["fulfilled"] += 1
                except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
                    pass
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        pass

    # Restock if low — buy from manufacturer
    try:
        ctx_resp = httpx.get(f"{RETAILER_URL}/api/agent/context", timeout=_TIMEOUT)
        if ctx_resp.status_code == 200:
            ctx = ctx_resp.json()
            for item in ctx.get("catalog", []):
                stock = item.get("stock_on_hand", 0)
                model = item.get("model_name", "")
                if stock < 5 and model:
                    try:
                        httpx.post(
                            f"{RETAILER_URL}/api/purchases",
                            json={"model": model, "quantity": 5},
                            timeout=_TIMEOUT,
                        )
                        actions["purchases"] += 1
                    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
                        pass
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        pass

    return actions


@router.post("/run-turn")
def run_turn(
    scenario_file: str = Query(
        default="scenarios/holiday-rush.json",
        description="Path to scenario file",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Run one simulation turn: autopilot decisions, inject demand, advance all.

    The manufacturer's advance_day() also advances the provider internally.
    Includes a simple autopilot that purchases materials, creates MOs,
    fulfills demands, and restocks the retailer.
    """
    # Load scenario and compute today's signal
    try:
        scenario = _get_scenario(scenario_file)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot load scenario: {exc}")

    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
        raise HTTPException(status_code=404, detail="Game state not found")
    if state.game_over:
        raise HTTPException(status_code=403, detail="Game is over")

    current_day = state.current_day
    signal = todays_signal(current_day, scenario)
    signal["day"] = current_day

    # 1. Inject customer demand into retailer
    demands_injected = 0
    try:
        demands_injected = generate_customer_orders(RETAILER_URL, signal, scenario)
    except Exception:
        pass  # degrade gracefully

    # 2. Autopilot: retailer fulfills orders + restocks
    retailer_actions = _autopilot_retailer()

    # 3. Autopilot: manufacturer purchases, produces, fulfills
    mfg_actions = _autopilot_manufacturer(db, current_day)

    # 4. Advance retailer
    try:
        httpx.post(
            f"{RETAILER_URL}/api/day/advance",
            timeout=_TIMEOUT,
        )
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        pass  # degrade gracefully

    # 5. Advance manufacturer (this also advances provider internally)
    try:
        adv_result = advance_day(db)
    except SimulationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Merge turn info
    turn_result = {
        "day": current_day,
        "demands_injected": demands_injected,
        "produced": adv_result.get("produced", 0),
        "deliveries": adv_result.get("deliveries", 0),
        "expired_demands": adv_result.get("expired_demands", 0),
        "autopilot": {
            "manufacturer": mfg_actions,
            "retailer": retailer_actions,
        },
    }

    return _build_combined_state(db, scenario_file=scenario_file, turn_result=turn_result)
