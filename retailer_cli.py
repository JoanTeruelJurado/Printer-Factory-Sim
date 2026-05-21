#!/usr/bin/env python3
"""
retailer-cli — Command-line interface for the Retailer API.

Usage:
  retailer-cli catalog                              List models and retail prices
  retailer-cli stock                                Show current inventory
  retailer-cli customers orders [--status STATUS]   List customer orders
  retailer-cli customers order ORDER_ID             Show order details
  retailer-cli fulfill ORDER_ID                     Fulfill a customer order
  retailer-cli backorder ORDER_ID                   Mark order as backordered
  retailer-cli purchase list [--status STATUS]      List purchase orders
  retailer-cli purchase create MODEL QTY            Order from manufacturer
  retailer-cli price set MODEL PRICE                Set retail price for a model
  retailer-cli day advance                          Advance one simulation day
  retailer-cli day current                          Show current simulation day
  retailer-cli export [FILE]                        Dump state to JSON
  retailer-cli import FILE                          Load state from JSON
  retailer-cli serve [--port 8003]                  Start the REST API

Environment:
  RETAILER_API_URL   Base URL of the Retailer API (default: http://localhost:8003)
"""

import argparse
import json
import os
import sys

import httpx

BASE_URL = os.getenv("RETAILER_API_URL", "http://localhost:8003")
TIMEOUT = httpx.Timeout(10.0)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(path: str, **params) -> dict | list:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.get(url, params=params or None, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Retailer API at {BASE_URL}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def _post(path: str, payload: dict | None = None) -> dict | list:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.post(url, json=payload or {}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Retailer API at {BASE_URL}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def _put(path: str, payload: dict) -> dict | list:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.put(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Retailer API at {BASE_URL}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


# ── Formatters ─────────────────────────────────────────────────────────────────

def _separator(char: str = "─", width: int = 72) -> str:
    return char * width


def _print_catalog(data: dict) -> None:
    items = data.get("items", [])
    print(_separator("═"))
    print(f"  {'ID':>4}  {'MODEL':<28} {'RETAIL':>10}  {'WHOLESALE':>10}")
    print(_separator())
    for c in items:
        print(
            f"  {c['id']:>4}  {c['model_name']:<28} "
            f"€{c['retail_price']:>9.2f}  €{c['wholesale_price']:>9.2f}"
        )
    print(_separator("═"))
    print(f"  Total: {len(items)} model(s)")


def _print_stock(data: dict) -> None:
    items = data.get("items", [])
    print(_separator("═"))
    print(f"  {'ID':>4}  {'MODEL':<28} {'QTY ON HAND':>12}")
    print(_separator())
    for s in items:
        print(f"  {s['id']:>4}  {s['model_name']:<28} {s['quantity_on_hand']:>12}")
    print(_separator("═"))
    print(f"  Total: {len(items)} item(s)")


def _print_customer_orders(data: dict) -> None:
    orders = data.get("orders", [])
    print(_separator("═"))
    print(f"  {'ID':>4}  {'CUSTOMER':<18} {'MODEL':<20} {'QTY':>4}  {'STATUS':<14}  {'DAY':>4}")
    print(_separator())
    for o in orders:
        fulfilled = f"  ful.d{o['fulfilled_day']:>3}" if o.get("fulfilled_day") else ""
        print(
            f"  {o['id']:>4}  {o['customer_name']:<18} {o['model_name']:<20} "
            f"{o['quantity']:>4}  {o['status']:<14}  d{o['order_day']:>3}{fulfilled}"
        )
    print(_separator("═"))
    print(f"  Total: {len(orders)} order(s)")


def _print_customer_order_detail(o: dict) -> None:
    print(_separator("═"))
    print(f"  Customer Order #{o['id']}")
    print(_separator())
    print(f"  Customer:      {o['customer_name']}")
    print(f"  Model:         {o['model_name']}")
    print(f"  Quantity:      {o['quantity']}")
    print(f"  Status:        {o['status']}")
    print(f"  Order day:     {o['order_day']}")
    print(f"  Fulfilled day: {o.get('fulfilled_day') or '—'}")
    print(_separator("═"))


def _print_purchase_orders(data: dict) -> None:
    orders = data.get("orders", [])
    print(_separator("═"))
    print(f"  {'ID':>4}  {'MODEL':<20} {'QTY':>5}  {'STATUS':<10}  {'ORDERED':>7}  {'EXP.DEL':>7}  {'TOTAL':>10}")
    print(_separator())
    for o in orders:
        print(
            f"  {o['id']:>4}  {o['model_name']:<20} {o['quantity']:>5}  "
            f"{o['status']:<10}  day {o['ordered_day']:>3}  day {o['expected_delivery_day']:>3}  "
            f"€{o['total_price']:>9.2f}"
        )
    print(_separator("═"))
    print(f"  Total: {len(orders)} order(s)")


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_catalog(args: argparse.Namespace) -> None:
    data = _get("/api/catalog")
    _print_catalog(data)


def cmd_stock(args: argparse.Namespace) -> None:
    data = _get("/api/stock")
    _print_stock(data)


def cmd_customers_orders(args: argparse.Namespace) -> None:
    params = {}
    if args.status:
        params["status"] = args.status
    data = _get("/api/orders", **params)
    _print_customer_orders(data)


def cmd_customers_order(args: argparse.Namespace) -> None:
    order = _get(f"/api/orders/{args.order_id}")
    _print_customer_order_detail(order)


def cmd_fulfill(args: argparse.Namespace) -> None:
    result = _post(f"/api/orders/{args.order_id}/fulfill")
    print(f"Order #{result['id']} fulfilled.")
    print(f"  Model:    {result['model_name']}")
    print(f"  Quantity: {result['quantity']}")
    print(f"  Status:   {result['status']}")


def cmd_backorder(args: argparse.Namespace) -> None:
    result = _post(f"/api/orders/{args.order_id}/backorder")
    print(f"Order #{result['id']} marked as backordered.")
    print(f"  Model:    {result['model_name']}")
    print(f"  Quantity: {result['quantity']}")
    print(f"  Status:   {result['status']}")


def cmd_purchase_list(args: argparse.Namespace) -> None:
    params = {}
    if args.status:
        params["status"] = args.status
    data = _get("/api/purchases", **params)
    _print_purchase_orders(data)


def cmd_purchase_create(args: argparse.Namespace) -> None:
    result = _post("/api/purchases", {"model": args.model, "quantity": args.quantity})
    print(f"Purchase order #{result['id']} created.")
    print(f"  Model:             {result['model_name']}")
    print(f"  Quantity:          {result['quantity']}")
    print(f"  Unit price:        €{result['unit_price']:.2f}")
    print(f"  Total price:       €{result['total_price']:.2f}")
    print(f"  Expected delivery: day {result['expected_delivery_day']}")


def cmd_price_set(args: argparse.Namespace) -> None:
    result = _put(f"/api/catalog/{args.model}/price", {"retail_price": args.price})
    print(f"Updated price for {result['model_name']}:")
    print(f"  Old price: €{result['old_price']:.2f}")
    print(f"  New price: €{result['new_price']:.2f}")


def cmd_day_advance(args: argparse.Namespace) -> None:
    result = _post("/api/day/advance")
    print(f"Day advanced → {result['new_day']}  (wallet: €{result['wallet_balance']:.2f})")
    summary = result.get("summary", {})
    if summary.get("deliveries_processed", 0) > 0:
        print(f"  Deliveries processed: {summary['deliveries_processed']} ({summary['units_received']} units)")
    if summary.get("backorders_fulfilled", 0) > 0:
        print(f"  Backorders fulfilled: {summary['backorders_fulfilled']} ({summary['backorder_units_fulfilled']} units)")
    if not summary.get("deliveries_processed") and not summary.get("backorders_fulfilled"):
        print("  No orders processed today.")


def cmd_day_current(args: argparse.Namespace) -> None:
    result = _get("/api/day/current")
    print(f"Retailer current day: {result['current_day']}")
    print(f"Wallet balance:       €{result['wallet_balance']:.2f}")


def cmd_export(args: argparse.Namespace) -> None:
    data = _get("/api/export")
    gs = data.get("game_state", {})
    out_file = getattr(args, "file", None) or f"retailer_export_day{gs.get('current_day', 0)}.json"
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported to {out_file}")


def cmd_import(args: argparse.Namespace) -> None:
    with open(args.file) as f:
        payload = json.load(f)
    result = _post("/api/import", payload)
    print(result.get("message", str(result)))


def cmd_serve(args: argparse.Namespace) -> None:
    port = args.port
    print(f"Starting Retailer API on port {port}...")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "retailer.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload",
    ])


# ── Parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retailer-cli",
        description="CLI for the Retailer API",
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    # catalog
    sub.add_parser("catalog", help="List models and retail prices")

    # stock
    sub.add_parser("stock", help="Show current inventory")

    # customers
    customers_p = sub.add_parser("customers", help="Manage customer orders")
    customers_sub = customers_p.add_subparsers(dest="action", required=True)

    co_list = customers_sub.add_parser("orders", help="List customer orders")
    co_list.add_argument("--status", default=None, help="Filter by status (pending/fulfilled/backordered/cancelled)")

    co_show = customers_sub.add_parser("order", help="Show order detail")
    co_show.add_argument("order_id", type=int, help="Order ID")

    # fulfill
    ful = sub.add_parser("fulfill", help="Fulfill a customer order from stock")
    ful.add_argument("order_id", type=int, help="Order ID")

    # backorder
    bo = sub.add_parser("backorder", help="Mark order as backordered")
    bo.add_argument("order_id", type=int, help="Order ID")

    # purchase
    purchase_p = sub.add_parser("purchase", help="Manage purchase orders")
    purchase_sub = purchase_p.add_subparsers(dest="action", required=True)

    pl = purchase_sub.add_parser("list", help="List purchase orders")
    pl.add_argument("--status", default=None, help="Filter by status (pending/shipped/delivered)")

    pc = purchase_sub.add_parser("create", help="Order from manufacturer")
    pc.add_argument("model", type=str, help="Printer model name")
    pc.add_argument("quantity", type=int, help="Number of units")

    # price
    price_p = sub.add_parser("price", help="Manage retail prices")
    price_sub = price_p.add_subparsers(dest="action", required=True)
    ps = price_sub.add_parser("set", help="Set retail price for a model")
    ps.add_argument("model", type=str, help="Model name")
    ps.add_argument("price", type=float, help="New retail price (€)")

    # day
    day_p = sub.add_parser("day", help="Simulation day commands")
    day_sub = day_p.add_subparsers(dest="action", required=True)
    day_sub.add_parser("advance", help="Advance one simulation day")
    day_sub.add_parser("current", help="Show current simulation day")

    # export
    exp = sub.add_parser("export", help="Export state to JSON")
    exp.add_argument("file", nargs="?", default=None, help="Output file (default: auto-named)")

    # import
    imp = sub.add_parser("import", help="Import state from JSON")
    imp.add_argument("file", help="JSON file to import")

    # serve
    srv = sub.add_parser("serve", help="Start the REST API server")
    srv.add_argument("--port", type=int, default=8003, help="Port (default: 8003)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        ("catalog",): cmd_catalog,
        ("stock",): cmd_stock,
        ("customers", "orders"): cmd_customers_orders,
        ("customers", "order"): cmd_customers_order,
        ("fulfill",): cmd_fulfill,
        ("backorder",): cmd_backorder,
        ("purchase", "list"): cmd_purchase_list,
        ("purchase", "create"): cmd_purchase_create,
        ("price", "set"): cmd_price_set,
        ("day", "advance"): cmd_day_advance,
        ("day", "current"): cmd_day_current,
        ("export",): cmd_export,
        ("import",): cmd_import,
        ("serve",): cmd_serve,
    }

    key = (args.resource,)
    if hasattr(args, "action"):
        key = (args.resource, args.action)

    fn = dispatch.get(key)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()
