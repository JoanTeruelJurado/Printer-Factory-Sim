"""Provider CLI — thin wrapper around the service layer.

Usage
-----
provider-cli catalog
provider-cli stock
provider-cli orders list [--status STATUS]
provider-cli orders show ORDER_ID
provider-cli price set PRODUCT_ID TIER_ID PRICE
provider-cli restock PRODUCT_ID QUANTITY
provider-cli day advance
provider-cli day current
provider-cli export [--output FILE]
provider-cli import FILE
provider-cli serve [--port PORT]
"""

import json
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# Ensure the provider package is importable when this script is run directly
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from provider_app.db import SessionLocal, init_db
from provider_app.services import catalog as catalog_svc
from provider_app.services import orders as orders_svc
from provider_app.services import simulation as sim_svc
from provider_app.services.seed import seed_initial_data

# ---------------------------------------------------------------------------
# App + sub-apps
# ---------------------------------------------------------------------------

app = typer.Typer(name="provider-cli", help="Provider App — CLI interface")
orders_app = typer.Typer(help="Manage purchase orders")
price_app = typer.Typer(help="Manage pricing tiers")
day_app = typer.Typer(help="Manage the simulation day")

app.add_typer(orders_app, name="orders")
app.add_typer(price_app, name="price")
app.add_typer(day_app, name="day")

console = Console()

STATUS_COLORS = {
    "pending": "yellow",
    "confirmed": "blue",
    "shipped": "cyan",
    "delivered": "green",
    "cancelled": "red",
}


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------


def _get_db():
    """Initialise DB (idempotent) and return a fresh session."""
    init_db()
    db = SessionLocal()
    seed_initial_data(db)
    return db


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------


@app.command("catalog")
def show_catalog():
    """List all products with pricing tiers."""
    db = _get_db()
    try:
        products = catalog_svc.get_catalog(db)
        table = Table(title="Provider Catalog", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Name", style="green", min_width=30)
        table.add_column("Lead", justify="center", width=6)
        table.add_column("Tier 1 (1–9)", justify="right")
        table.add_column("Tier 2 (10–49)", justify="right")
        table.add_column("Tier 3 (50+)", justify="right")

        for p in products:
            tiers = sorted(p.pricing_tiers, key=lambda t: t.min_qty)
            prices = [f"€{t.price_per_unit:.2f}" for t in tiers]
            while len(prices) < 3:
                prices.append("-")
            table.add_row(str(p.id), p.name, f"{p.lead_time_days}d", *prices[:3])

        console.print(table)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# stock
# ---------------------------------------------------------------------------


@app.command("stock")
def show_stock():
    """Show current inventory levels."""
    db = _get_db()
    try:
        stocks = catalog_svc.get_stock(db)
        table = Table(title="Current Stock", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Product", style="green", min_width=30)
        table.add_column("Quantity", justify="right", style="bold")

        for s in stocks:
            qty_color = "red" if s.quantity < 50 else "yellow" if s.quantity < 100 else "green"
            table.add_row(
                str(s.product_id),
                s.product.name,
                f"[{qty_color}]{s.quantity}[/{qty_color}]",
            )

        console.print(table)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------


@orders_app.command("list")
def orders_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List all orders, optionally filtered by status."""
    db = _get_db()
    try:
        order_list = orders_svc.list_orders(db, status)
        title = f"Orders [{status}]" if status else "All Orders"
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=5)
        table.add_column("Buyer", style="green")
        table.add_column("Product", min_width=25)
        table.add_column("Qty", justify="right", width=5)
        table.add_column("Total", justify="right")
        table.add_column("Placed", justify="center", width=7)
        table.add_column("Expect", justify="center", width=7)
        table.add_column("Status")

        for o in order_list:
            color = STATUS_COLORS.get(o.status, "white")
            table.add_row(
                str(o.id),
                o.buyer_name,
                o.product.name,
                str(o.quantity),
                f"€{o.total_price:.2f}",
                str(o.placed_day),
                str(o.expected_delivery_day),
                f"[{color}]{o.status}[/{color}]",
            )

        console.print(table)
        console.print(f"[dim]Total: {len(order_list)} order(s)[/dim]")
    finally:
        db.close()


@orders_app.command("show")
def orders_show(order_id: int = typer.Argument(..., help="Order ID")):
    """Show full details of one order."""
    db = _get_db()
    try:
        order = orders_svc.get_order(db, order_id)
        color = STATUS_COLORS.get(order.status, "white")
        console.print(f"\n[bold cyan]Order #{order.id}[/bold cyan]")
        console.print(f"  Buyer              : {order.buyer_name}")
        console.print(f"  Product            : {order.product.name}")
        console.print(f"  Quantity           : {order.quantity}")
        console.print(f"  Unit price         : €{order.unit_price:.2f}")
        console.print(f"  Total price        : €{order.total_price:.2f}")
        console.print(f"  Placed day         : {order.placed_day}")
        console.print(f"  Expected delivery  : {order.expected_delivery_day}")
        console.print(f"  Confirmed day      : {order.confirmed_day or '–'}")
        console.print(f"  Shipped day        : {order.shipped_day or '–'}")
        console.print(f"  Delivered day      : {order.delivered_day or '–'}")
        console.print(f"  Status             : [{color}]{order.status}[/{color}]")
        console.print()
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# price
# ---------------------------------------------------------------------------


@price_app.command("set")
def price_set(
    product_id: int = typer.Argument(..., help="Product ID"),
    tier_id: int = typer.Argument(..., help="Pricing tier ID"),
    price: float = typer.Argument(..., help="New price per unit (EUR)"),
):
    """Update the price for a specific tier of a product."""
    db = _get_db()
    try:
        current_day = sim_svc.get_current_day(db)
        tier = catalog_svc.set_price(db, product_id, tier_id, price, current_day)
        console.print(
            f"[green]Price updated[/green]: product {product_id}, "
            f"tier {tier_id} (qty {tier.min_qty}–{tier.max_qty or '∞'}) "
            f"→ €{price:.2f}"
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# restock
# ---------------------------------------------------------------------------


@app.command("restock")
def do_restock(
    product_id: int = typer.Argument(..., help="Product ID"),
    quantity: int = typer.Argument(..., help="Units to add"),
):
    """Add units to a product's stock (simulates upstream delivery)."""
    db = _get_db()
    try:
        current_day = sim_svc.get_current_day(db)
        stock = catalog_svc.restock(db, product_id, quantity, current_day)
        product = db.query(__import__("provider_app.models", fromlist=["Product"]).Product).filter_by(id=product_id).first()
        name = product.name if product else f"product {product_id}"
        console.print(
            f"[green]Restocked[/green] {name}: +{quantity} → total {stock.quantity}"
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# day
# ---------------------------------------------------------------------------


@day_app.command("advance")
def day_advance():
    """Advance the simulation by one day and process all order transitions."""
    db = _get_db()
    try:
        result = sim_svc.advance_day(db)
        console.print(
            f"[green]Day advanced[/green]: "
            f"{result['previous_day']} → [bold]{result['current_day']}[/bold]"
        )
        if result["transitions"]:
            console.print("  Order transitions:")
            for t in result["transitions"]:
                console.print(f"    Order #{t['order_id']}: {t['transition']}")
        else:
            console.print("  [dim]No order transitions[/dim]")
    finally:
        db.close()


@day_app.command("current")
def day_current():
    """Show the current simulation day."""
    db = _get_db()
    try:
        day = sim_svc.get_current_day(db)
        console.print(f"Current simulation day: [bold cyan]{day}[/bold cyan]")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# export / import
# ---------------------------------------------------------------------------


@app.command("export")
def do_export(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
):
    """Dump the full provider state to JSON."""
    db = _get_db()
    try:
        from provider_app.models import Product, ProviderOrder, Stock

        data = {
            "simulation_day": sim_svc.get_current_day(db),
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "lead_time_days": p.lead_time_days,
                    "active": p.active,
                    "pricing_tiers": [
                        {
                            "id": t.id,
                            "min_qty": t.min_qty,
                            "max_qty": t.max_qty,
                            "price_per_unit": t.price_per_unit,
                        }
                        for t in sorted(p.pricing_tiers, key=lambda t: t.min_qty)
                    ],
                    "stock": (
                        db.query(Stock).filter_by(product_id=p.id).first().quantity
                        if db.query(Stock).filter_by(product_id=p.id).first()
                        else 0
                    ),
                }
                for p in db.query(Product).all()
            ],
            "orders": [
                {
                    "id": o.id,
                    "buyer_name": o.buyer_name,
                    "product_id": o.product_id,
                    "product_name": o.product.name,
                    "quantity": o.quantity,
                    "unit_price": o.unit_price,
                    "total_price": o.total_price,
                    "placed_day": o.placed_day,
                    "expected_delivery_day": o.expected_delivery_day,
                    "confirmed_day": o.confirmed_day,
                    "shipped_day": o.shipped_day,
                    "delivered_day": o.delivered_day,
                    "status": o.status,
                    "created_at": o.created_at.isoformat(),
                }
                for o in db.query(ProviderOrder).all()
            ],
        }

        json_str = json.dumps(data, indent=2)
        if output:
            with open(output, "w") as f:
                f.write(json_str)
            console.print(f"[green]Exported to {output}[/green]")
        else:
            print(json_str)
    finally:
        db.close()


@app.command(name="import")
def do_import(file: str = typer.Argument(..., help="JSON file to import")):
    """Load provider state from a JSON file (replaces current state)."""
    db = _get_db()
    try:
        with open(file) as f:
            data = json.load(f)

        from datetime import datetime

        from provider_app.models import (
            PricingTier,
            Product,
            ProviderOrder,
            SimulationDay,
            Stock,
        )

        db.query(ProviderOrder).delete()
        db.query(Stock).delete()
        db.query(PricingTier).delete()
        db.query(Product).delete()

        sim = db.query(SimulationDay).filter_by(id=1).first()
        if sim:
            sim.current_day = data.get("simulation_day", 1)
        else:
            db.add(SimulationDay(id=1, current_day=data.get("simulation_day", 1)))

        for p_data in data.get("products", []):
            product = Product(
                id=p_data["id"],
                name=p_data["name"],
                description=p_data.get("description"),
                lead_time_days=p_data["lead_time_days"],
                active=bool(p_data.get("active", True)),
            )
            db.add(product)
            db.flush()

            for t_data in p_data.get("pricing_tiers", []):
                db.add(
                    PricingTier(
                        id=t_data.get("id"),
                        product_id=product.id,
                        min_qty=t_data["min_qty"],
                        max_qty=t_data.get("max_qty"),
                        price_per_unit=t_data["price_per_unit"],
                    )
                )

            db.add(Stock(product_id=product.id, quantity=p_data.get("stock", 0)))

        for o_data in data.get("orders", []):
            db.add(
                ProviderOrder(
                    id=o_data["id"],
                    buyer_name=o_data["buyer_name"],
                    product_id=o_data["product_id"],
                    quantity=o_data["quantity"],
                    unit_price=o_data["unit_price"],
                    total_price=o_data["total_price"],
                    placed_day=o_data["placed_day"],
                    expected_delivery_day=o_data["expected_delivery_day"],
                    confirmed_day=o_data.get("confirmed_day"),
                    shipped_day=o_data.get("shipped_day"),
                    delivered_day=o_data.get("delivered_day"),
                    status=o_data["status"],
                    created_at=datetime.fromisoformat(o_data["created_at"]),
                )
            )

        db.commit()
        console.print(f"[green]State imported from {file}[/green]")
    except Exception as exc:
        db.rollback()
        console.print(f"[red]Import failed: {exc}[/red]")
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@app.command("serve")
def serve(
    port: int = typer.Option(8001, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
):
    """Start the Provider REST API server."""
    import uvicorn

    console.print(f"[green]Provider API starting on http://{host}:{port}[/green]")
    console.print(f"[blue]Swagger docs: http://localhost:{port}/docs[/blue]")
    uvicorn.run("provider_app.api:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
