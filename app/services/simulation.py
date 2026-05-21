"""
Core simulation engine for the 3D Printer Factory Simulator.

Handles day advancement, demand generation, production processing,
purchase deliveries, demand fulfillment, and cost calculation.
"""

import json
import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import (
    DemandOrder,
    DailyCosts,
    Event,
    GameState,
    Inventory,
    LocalPurchaseOrder,
    ManufacturingOrder,
    Product,
    SalesOrder,
)
from app.services import supplier_client
from app.services.supplier_client import SupplierAPIError


class SimulationError(Exception):
    """Base exception for simulation errors."""
    pass


class InsufficientFundsError(SimulationError):
    """Raised when wallet has insufficient funds."""
    pass


class CapacityExceededError(SimulationError):
    """Raised when warehouse or production capacity exceeded."""
    pass


class MaterialShortageError(SimulationError):
    """Raised when required materials are not available."""
    pass


def log_event(
    db: Session,
    event_type: str,
    sim_day: int,
    category: str,
    details: dict,
) -> None:
    """
    Log an event to the events table.
    
    Args:
        db: Database session
        event_type: Type of event (e.g., "DEMAND_GENERATED")
        sim_day: Simulation day number
        category: Event category (production, purchase, demand, inventory, financial, system, alert)
        details: JSON-serializable dict with event-specific data
    """
    event = Event(
        event_type=event_type,
        sim_day=sim_day,
        timestamp=datetime.utcnow(),
        details=json.dumps(details),
        category=category,
    )
    db.add(event)


def generate_demand_orders(db: Session, current_day: int) -> int:
    """
    Generate random demand orders for the current day.
    
    Generates 0-5 orders with random products and due dates.
    
    Args:
        db: Database session
        current_day: Current simulation day
        
    Returns:
        Number of demand orders created
    """
    num_orders = random.randint(1, 2)
    orders_created = 0
    
    if num_orders == 0:
        return 0
    
    finished_products = db.query(Product).filter_by(product_type="finished").all()
    if not finished_products:
        return 0
    
    for _ in range(num_orders):
        product = random.choice(finished_products)
        quantity = random.randint(1, 5)
        due_day = current_day + random.randint(3, 7)
        
        # Create a generic client (id=1 for now, can expand later)
        demand = DemandOrder(
            client_id=1,
            product_id=product.id,
            quantity=quantity,
            request_day=current_day,
            due_day=due_day,
            status="open",
            fulfilled_qty=0,
        )
        db.add(demand)
        orders_created += 1
    
    db.flush()
    log_event(
        db,
        "DEMAND_GENERATED",
        current_day,
        "demand",
        {"num_orders": orders_created},
    )
    
    return orders_created


def process_purchase_deliveries(db: Session, current_day: int) -> int:
    """
    Process purchase orders that are due to arrive today.

    Fetches due orders from the Supplier API, updates local inventory,
    then marks each order as delivered in the Supplier API.

    Args:
        db: Database session
        current_day: Current simulation day

    Returns:
        Number of purchase orders delivered
    """
    try:
        due_orders = supplier_client.get_due_orders(current_day)
    except SupplierAPIError:
        # If Supplier API is unavailable, skip deliveries gracefully
        return 0

    delivered_count = 0

    for po in due_orders:
        material_id = po["material_id"]
        quantity = po["quantity"]

        # Add materials to local inventory
        inventory = db.query(Inventory).filter_by(material_id=material_id).first()
        if inventory:
            inventory.quantity += quantity

        # Mark order as delivered in Supplier API
        try:
            supplier_client.deliver_order(po["id"], current_day)
        except SupplierAPIError:
            # Log but continue processing other orders
            pass

        # Update local copy
        local_po = db.query(LocalPurchaseOrder).filter_by(supplier_po_id=po["id"]).first()
        if local_po:
            local_po.status = "delivered"
            local_po.actual_delivery_day = current_day

        delivered_count += 1

        log_event(
            db,
            "PURCHASE_DELIVERED",
            current_day,
            "purchase",
            {
                "po_id": po["id"],
                "material_id": material_id,
                "material_name": po.get("material_name", str(material_id)),
                "quantity": quantity,
                "cost": po["total_cost"],
            },
        )

    return delivered_count


def process_production(db: Session, current_day: int) -> dict:
    """
    Process production of released manufacturing orders.
    
    Consumes materials, produces finished goods, and updates order status.
    
    Args:
        db: Database session
        current_day: Current simulation day
        
    Returns:
        Dict with production stats (produced, cost)
    """
    game_state = db.query(GameState).filter_by(id=1).first()
    daily_costs = db.query(DailyCosts).filter_by(id=1).first()
    
    if not game_state or not daily_costs:
        raise SimulationError("Game state or daily costs not found")
    
    released_orders = db.query(ManufacturingOrder).filter_by(
        status="released"
    ).all()
    
    total_produced = 0
    total_production_cost = 0.0
    total_assembly_hours = 0.0
    
    for order in released_orders:
        remaining_capacity = game_state.daily_production_capacity - total_produced
        if remaining_capacity <= 0:
            break
        
        # How many units can we produce of this order?
        units_to_produce = min(order.remaining_qty, int(remaining_capacity))
        if units_to_produce == 0:
            continue
        
        # Check material availability
        bom_lines = order.product.bom_lines
        can_produce = True
        
        for bom in bom_lines:
            required = bom.qty_needed * units_to_produce
            available = (bom.material.inventory.quantity 
                        if bom.material.inventory else 0)
            
            if available < required:
                can_produce = False
                break
        
        if not can_produce:
            continue
        
        # Consume materials
        for bom in bom_lines:
            required = bom.qty_needed * units_to_produce
            bom.material.inventory.quantity -= required
            bom.material.inventory.reserved_quantity -= required
        
        # Update order
        order.remaining_qty -= units_to_produce
        total_produced += units_to_produce
        
        # Calculate production cost
        variable_cost = units_to_produce * daily_costs.variable_cost_per_unit
        assembly_cost = (units_to_produce * order.product.assembly_time_hours * 
                        daily_costs.energy_cost_per_hour)
        total_production_cost += variable_cost + assembly_cost
        total_assembly_hours += units_to_produce * order.product.assembly_time_hours
        
        # If order is fully completed, mark as such
        if order.remaining_qty == 0:
            order.status = "completed"
            order.completed_day = current_day
            log_event(
                db,
                "ORDER_COMPLETED",
                current_day,
                "production",
                {
                    "order_id": order.id,
                    "product_id": order.product_id,
                    "product_name": order.product.name,
                    "quantity": order.quantity,
                },
            )
        else:
            log_event(
                db,
                "ORDER_PARTIALLY_COMPLETED",
                current_day,
                "production",
                {
                    "order_id": order.id,
                    "product_id": order.product_id,
                    "produced": units_to_produce,
                    "remaining": order.remaining_qty,
                },
            )
    
    # Add fixed costs
    total_cost = (daily_costs.fixed_cost + total_production_cost)
    
    # Add maintenance percentage
    maintenance_cost = total_cost * daily_costs.maintenance_percentage
    total_cost += maintenance_cost
    
    return {
        "produced": total_produced,
        "cost": total_cost,
        "assembly_hours": total_assembly_hours,
    }


def fulfill_demand_orders(db: Session, current_day: int) -> dict:
    """
    Match completed manufacturing orders to open demand orders.
    
    Fulfills demand in FIFO order by demand creation date.
    
    Args:
        db: Database session
        current_day: Current simulation day
        
    Returns:
        Dict with fulfillment stats (fulfilled, revenue, penalties)
    """
    # Get completed manufacturing orders
    completed_orders = db.query(ManufacturingOrder).filter_by(
        status="completed"
    ).all()
    
    # Get available finished goods (sum of all completed production)
    available_goods: dict[int, int] = {}
    for order in completed_orders:
        product_id = order.product_id
        available_goods[product_id] = available_goods.get(product_id, 0) + order.quantity
    
    # Get open demand orders, sorted by due date
    open_demands = db.query(DemandOrder).filter(
        DemandOrder.status.in_(["open", "partial"])
    ).order_by(DemandOrder.due_day).all()
    
    total_revenue = 0.0
    total_penalties = 0.0
    
    for demand in open_demands:
        if demand.product_id not in available_goods:
            continue
        
        available = available_goods[demand.product_id]
        needed = demand.quantity - demand.fulfilled_qty
        
        if needed <= 0:
            continue
        
        # How many can we fulfill?
        fulfilled_qty = min(needed, available)
        demand.fulfilled_qty += fulfilled_qty
        available_goods[demand.product_id] -= fulfilled_qty
        
        # Calculate revenue
        revenue = fulfilled_qty * demand.product.sell_price
        total_revenue += revenue
        
        # Update demand status
        if demand.fulfilled_qty == demand.quantity:
            demand.status = "fulfilled"
            log_event(
                db,
                "DEMAND_FULFILLED",
                current_day,
                "demand",
                {
                    "demand_id": demand.id,
                    "product_id": demand.product_id,
                    "quantity": demand.quantity,
                    "revenue": revenue,
                },
            )
        else:
            demand.status = "partial"
            
            # Apply penalty for partial/late fulfillment
            if current_day >= demand.due_day:
                penalty = (demand.quantity - demand.fulfilled_qty) * 50  # €50 per unit penalty
                demand.penalty_amount = penalty
                total_penalties += penalty
                log_event(
                    db,
                    "DEMAND_LATE_PENALTY",
                    current_day,
                    "financial",
                    {
                        "demand_id": demand.id,
                        "days_late": current_day - demand.due_day,
                        "penalty": penalty,
                    },
                )
    
    # Mark unfulfilled demands as lost if past due date
    for demand in open_demands:
        if demand.status == "open" and current_day > demand.due_day:
            demand.status = "lost"
            penalty = demand.quantity * 50  # €50 per unit penalty
            demand.penalty_amount = penalty
            total_penalties += penalty
            log_event(
                db,
                "DEMAND_LOST",
                current_day,
                "alert",
                {
                    "demand_id": demand.id,
                    "product_id": demand.product_id,
                    "quantity": demand.quantity,
                    "penalty": penalty,
                },
            )
    
    return {
        "revenue": total_revenue,
        "penalties": total_penalties,
    }


def mark_expired_demands(db: Session, current_day: int) -> int:
    """Mark open demand orders past their due date as lost and apply penalties."""
    expired = db.query(DemandOrder).filter(
        DemandOrder.status.in_(["open", "partial"]),
        DemandOrder.due_day < current_day,
    ).all()

    if not expired:
        return 0

    game_state = db.query(GameState).filter_by(id=1).first()

    for demand in expired:
        unfulfilled = demand.quantity - demand.fulfilled_qty
        penalty = unfulfilled * 50  # €50 per unfulfilled unit
        demand.status = "lost"
        demand.penalty_amount = penalty
        if game_state:
            game_state.wallet_balance -= penalty
        log_event(
            db,
            "DEMAND_EXPIRED",
            current_day,
            "alert",
            {
                "demand_id": demand.id,
                "product_id": demand.product_id,
                "quantity": demand.quantity,
                "unfulfilled": unfulfilled,
                "penalty": penalty,
            },
        )
        if penalty > 0:
            log_event(
                db,
                "PENALTY_DEDUCTED",
                current_day,
                "financial",
                {"demand_id": demand.id, "penalty": penalty},
            )

    return len(expired)


def calculate_daily_costs(db: Session, current_day: int) -> float:
    """
    Calculate and deduct daily operational costs.
    
    Includes fixed costs, variable costs, and maintenance.
    Production costs are calculated separately during production.
    
    Args:
        db: Database session
        current_day: Current simulation day
        
    Returns:
        Total cost deducted
    """
    daily_costs = db.query(DailyCosts).filter_by(id=1).first()
    if not daily_costs:
        return 0.0
    
    # Fixed costs only (variable/production costs calculated in process_production)
    cost = daily_costs.fixed_cost
    
    game_state = db.query(GameState).filter_by(id=1).first()
    game_state.wallet_balance -= cost
    
    log_event(
        db,
        "DAILY_COST_DEDUCTED",
        current_day,
        "financial",
        {
            "fixed_cost": daily_costs.fixed_cost,
        },
    )
    
    return cost


def apply_daily_price_fluctuation(db: Session) -> None:
    """
    Apply daily price fluctuation to supplier products.

    Delegates to the Supplier API which recalculates daily_price_factor
    (±10% random variation) for all supplier-material combinations.

    Args:
        db: Database session (unused here; kept for signature compatibility)
    """
    try:
        supplier_client.fluctuate_prices()
    except SupplierAPIError:
        # If Supplier API is unavailable, skip fluctuation gracefully
        pass


def check_game_over(db: Session, current_day: int) -> bool:
    """
    Check if game over conditions are met.
    
    Game ends if wallet goes negative for 3+ consecutive days.
    
    Args:
        db: Database session
        current_day: Current simulation day
        
    Returns:
        True if game is over, False otherwise
    """
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        return False
    
    if game_state.wallet_balance < 0:
        game_state.days_with_negative_balance += 1
        
        if game_state.days_with_negative_balance >= 3:
            game_state.game_over = True
            log_event(
                db,
                "GAME_OVER",
                current_day,
                "alert",
                {
                    "reason": "Negative wallet balance for 3 consecutive days",
                    "wallet": game_state.wallet_balance,
                },
            )
            return True
        else:
            log_event(
                db,
                "WALLET_NEGATIVE",
                current_day,
                "alert",
                {
                    "wallet": game_state.wallet_balance,
                    "days_negative": game_state.days_with_negative_balance,
                },
            )
    else:
        game_state.days_with_negative_balance = 0
    
    return False


def process_sales_production(db: Session, current_day: int, remaining_capacity: int) -> dict:
    """
    Process released sales orders: consume materials and produce finished goods.

    Shares the same daily_production_capacity as ManufacturingOrders.
    Called AFTER process_production so remaining capacity is what MOs left.

    Args:
        db: Database session
        current_day: Current simulation day
        remaining_capacity: Units of capacity left after MO production

    Returns:
        Dict with production stats (produced, cost, assembly_hours, capacity_used)
    """
    daily_costs = db.query(DailyCosts).filter_by(id=1).first()
    if not daily_costs:
        return {"produced": 0, "cost": 0.0, "assembly_hours": 0.0, "capacity_used": 0}

    released_orders = db.query(SalesOrder).filter_by(status="released").all()

    total_produced = 0
    total_production_cost = 0.0
    total_assembly_hours = 0.0

    for order in released_orders:
        cap_left = remaining_capacity - total_produced
        if cap_left <= 0:
            break

        units_to_produce = min(order.quantity, int(cap_left))
        if units_to_produce == 0:
            continue

        # Check material availability (materials should be reserved already)
        bom_lines = order.product.bom_lines
        can_produce = True

        for bom in bom_lines:
            required = bom.qty_needed * units_to_produce
            available = (bom.material.inventory.quantity
                        if bom.material.inventory else 0)
            if available < required:
                can_produce = False
                break

        if not can_produce:
            continue

        # Consume materials (and reduce reserved)
        for bom in bom_lines:
            required = bom.qty_needed * units_to_produce
            bom.material.inventory.quantity -= required
            bom.material.inventory.reserved_quantity -= required

        total_produced += units_to_produce

        # Calculate production cost
        variable_cost = units_to_produce * daily_costs.variable_cost_per_unit
        assembly_cost = (units_to_produce * order.product.assembly_time_hours *
                        daily_costs.energy_cost_per_hour)
        total_production_cost += variable_cost + assembly_cost
        total_assembly_hours += units_to_produce * order.product.assembly_time_hours

        # Sales orders don't support partial production — only complete if all units done
        if units_to_produce == order.quantity:
            order.status = "completed"
            order.completed_day = current_day
            log_event(
                db,
                "SALES_ORDER_COMPLETED",
                current_day,
                "production",
                {
                    "sales_order_id": order.id,
                    "product_id": order.product_id,
                    "product_name": order.product.name,
                    "quantity": order.quantity,
                },
            )

    return {
        "produced": total_produced,
        "cost": total_production_cost,
        "assembly_hours": total_assembly_hours,
        "capacity_used": total_produced,
    }


def process_sales_shipping(db: Session, current_day: int) -> dict:
    """
    Ship completed sales orders. Revenue is collected on shipping.

    For each completed sales order, check if there are enough finished goods
    (completed MO quantities minus already-shipped sales order quantities).
    If available, mark as shipped and add revenue to wallet.

    Args:
        db: Database session
        current_day: Current simulation day

    Returns:
        Dict with shipping stats (shipped_count, revenue)
    """
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        return {"shipped_count": 0, "revenue": 0.0}

    # Calculate finished goods per product:
    # completed MO quantities - shipped/delivered sales order quantities
    completed_mos = db.query(ManufacturingOrder).filter_by(status="completed").all()
    finished_goods: dict[int, int] = {}
    for mo in completed_mos:
        finished_goods[mo.product_id] = finished_goods.get(mo.product_id, 0) + mo.quantity

    # Subtract already shipped/delivered sales order quantities
    shipped_sales = db.query(SalesOrder).filter(
        SalesOrder.status.in_(["shipped", "delivered"])
    ).all()
    for so in shipped_sales:
        finished_goods[so.product_id] = finished_goods.get(so.product_id, 0) - so.quantity

    # Process completed sales orders
    completed_orders = db.query(SalesOrder).filter_by(status="completed").all()
    shipped_count = 0
    total_revenue = 0.0

    for order in completed_orders:
        available = finished_goods.get(order.product_id, 0)
        if available >= order.quantity:
            order.status = "shipped"
            order.shipped_day = current_day
            game_state.wallet_balance += order.total_price
            finished_goods[order.product_id] -= order.quantity
            shipped_count += 1
            total_revenue += order.total_price

            log_event(
                db,
                "SALES_ORDER_SHIPPED",
                current_day,
                "financial",
                {
                    "sales_order_id": order.id,
                    "product_id": order.product_id,
                    "product_name": order.product.name,
                    "quantity": order.quantity,
                    "revenue": order.total_price,
                },
            )

    return {
        "shipped_count": shipped_count,
        "revenue": total_revenue,
    }


def advance_day(db: Session) -> dict:
    """
    Advance simulation by one day.
    
    Orchestrates the complete daily cycle:
    1. Apply daily price fluctuation
    2. Generate new demand orders
    3. Process purchase deliveries
    4. Process production
    5. Fulfill demand orders
    6. Calculate daily costs
    7. Check game over condition
    
    Args:
        db: Database session
        
    Returns:
        Dict with daily simulation results
        
    Raises:
        SimulationError: If any step fails
    """
    game_state = db.query(GameState).filter_by(id=1).first()
    if not game_state:
        raise SimulationError("Game state not found")
    
    try:
        current_day = game_state.current_day
        
        # 1. Apply price fluctuation
        apply_daily_price_fluctuation(db)

        # 2. Advance the supplier's day so pending orders ship and due orders are delivered
        supplier_day_result = {}
        try:
            supplier_day_result = supplier_client.advance_supplier_day()
        except SupplierAPIError:
            pass

        # 3. Generate demand
        demands_created = generate_demand_orders(db, current_day)

        # 4. Process purchase deliveries (picks up orders the supplier just marked delivered)
        deliveries = process_purchase_deliveries(db, current_day)
        
        # 5. Process production (ManufacturingOrders)
        production_stats = process_production(db, current_day)

        # 6. Process sales order production (released SalesOrders consume materials)
        remaining_capacity = game_state.daily_production_capacity - production_stats["produced"]
        sales_production_stats = process_sales_production(db, current_day, remaining_capacity)

        # 7. Ship completed sales orders (completed → shipped, revenue collected)
        sales_shipping_stats = process_sales_shipping(db, current_day)

        # 8. Mark expired demand orders as lost (manual fulfillment — no auto-revenue)
        expired = mark_expired_demands(db, current_day)

        # 9. Calculate costs
        calculate_daily_costs(db, current_day)

        # Deduct production costs (MO + sales order production)
        total_production_cost = production_stats["cost"] + sales_production_stats["cost"]
        game_state.wallet_balance -= total_production_cost

        delayed_deliveries = supplier_day_result.get("delayed_count", 0)

        log_event(
            db,
            "DAY_SUMMARY",
            current_day,
            "financial",
            {
                "demands_created": demands_created,
                "deliveries": deliveries,
                "delayed_deliveries": delayed_deliveries,
                "produced": production_stats["produced"] + sales_production_stats["produced"],
                "production_cost": total_production_cost,
                "sales_produced": sales_production_stats["produced"],
                "sales_shipped": sales_shipping_stats["shipped_count"],
                "sales_revenue": sales_shipping_stats["revenue"],
                "expired_demands": expired,
                "wallet_balance": game_state.wallet_balance,
            },
        )
        
        # 7. Check game over
        is_game_over = check_game_over(db, current_day)
        
        # 8. Advance day counter
        game_state.current_day += 1
        game_state.last_updated = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "day": current_day,
            "demands_created": demands_created,
            "deliveries": deliveries,
            "delayed_deliveries": delayed_deliveries,
            "produced": production_stats["produced"] + sales_production_stats["produced"],
            "production_cost": total_production_cost,
            "sales_produced": sales_production_stats["produced"],
            "sales_shipped": sales_shipping_stats["shipped_count"],
            "sales_revenue": sales_shipping_stats["revenue"],
            "expired_demands": expired,
            "wallet_balance": game_state.wallet_balance,
            "game_over": is_game_over,
        }
        
    except Exception as e:
        db.rollback()
        log_event(
            db,
            "SIMULATION_ERROR",
            game_state.current_day,
            "system",
            {"error": str(e)},
        )
        raise SimulationError(f"Simulation failed: {str(e)}") from e
