#!/usr/bin/env python3
"""
provider-cli — Command-line interface for the Supplier API (provider).

Usage:
  provider-cli catalog                              List products with pricing tiers
  provider-cli stock                                Show current inventory
  provider-cli orders list [--status STATUS]        List orders (optional status filter)
  provider-cli orders show ORDER_ID                 Details of one order
  provider-cli price set TIER_ID PRICE              Change a pricing tier
  provider-cli restock SP_ID QUANTITY               Add to supplier stock
  provider-cli day advance                          Process one simulation day
  provider-cli day current                          Show current simulation day
  provider-cli export [FILE]                        Dump state to JSON
  provider-cli import FILE                          Load state from JSON
  provider-cli serve [--port 8001]                  Start the REST API

Environment:
  SUPPLIER_API_URL   Base URL of the Supplier API (default: http://localhost:8001)
"""

import argparse
import json
import os
import sys

import httpx

BASE_URL = os.getenv("SUPPLIER_API_URL", "http://localhost:8001")
TIMEOUT = httpx.Timeout(10.0)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(path: str, **params) -> dict | list:
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.get(url, params=params or None, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach Supplier API at {BASE_URL}", file=sys.stderr)
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
        print(f"ERROR: Cannot reach Supplier API at {BASE_URL}", file=sys.stderr)
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
        print(f"ERROR: Cannot reach Supplier API at {BASE_URL}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


# ── Formatters ─────────────────────────────────────────────────────────────────

def _separator(char: str = "─", width: int = 72) -> str:
    return char * width


def _print_catalog(entries: list) -> None:
    print(_separator("═"))
    print(f"  {'SUPPLIER':<28} {'MATERIAL':<28} {'STOCK':>6}  {'LEAD':>4}")
    print(_separator())
    for e in entries:
        print(f"  [{e['supplier_id']}] {e['supplier_name']:<26} {e['material_name']:<28} {e['stock']:>6}  {e['lead_time_days']:>3}d")
        for t in e["pricing_tiers"]:
            print(f"      tier #{t['id']:>3}  min_qty={t['min_quantity']:>4}  unit_price=€{t['unit_price']:>8.2f}")
    print(_separator("═"))


def _print_stock(items: list) -> None:
    print(_separator("═"))
    print(f"  {'SUPPLIER':<28} {'MATERIAL':<28} {'QTY':>8}")
    print(_separator())
    for s in items:
        print(f"  [{s['supplier_id']}] {s['supplier_name']:<26} {s['material_name']:<28} {s['quantity']:>8}")
    print(_separator("═"))


def _print_orders(orders: list) -> None:
    print(_separator("═"))
    print(f"  {'ID':>4}  {'MATERIAL':<28} {'QTY':>5}  {'STATUS':<10}  {'ISSUED':>6}  {'EXP.DEL':>7}  {'COST':>10}")
    print(_separator())
    for o in orders:
        print(
            f"  {o['id']:>4}  {o['material_name']:<28} {o['quantity']:>5}  "
            f"{o['status']:<10}  day {o['issue_day']:>3}  day {o['expected_delivery_day']:>3}  "
            f"€{o['total_cost']:>9.2f}"
        )
    print(_separator("═"))
    print(f"  Total: {len(orders)} order(s)")


def _print_order_detail(o: dict) -> None:
    print(_separator("═"))
    print(f"  Order #{o['id']}")
    print(_separator())
    print(f"  Buyer:             {o.get('buyer') or '—'}")
    print(f"  Material:          {o['material_name']} (id={o['material_id']})")
    print(f"  Quantity:          {o['quantity']}")
    print(f"  Unit cost:         €{o['unit_cost']:.2f}")
    print(f"  Total cost:        €{o['total_cost']:.2f}")
    print(f"  Status:            {o['status']}")
    print(f"  Issued day:        {o['issue_day']}")
    print(f"  Expected delivery: day {o['expected_delivery_day']}")
    print(f"  Shipped day:       {o.get('shipped_day') or '—'}")
    print(f"  Delivered day:     {o.get('actual_delivery_day') or '—'}")
    print(_separator("═"))


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_catalog(args: argparse.Namespace) -> None:
    entries = _get("/api/catalog")
    _print_catalog(entries)


def cmd_stock(args: argparse.Namespace) -> None:
    items = _get("/api/stock")
    _print_stock(items)


def cmd_orders_list(args: argparse.Namespace) -> None:
    params = {}
    if args.status:
        params["status"] = args.status
    orders = _get("/api/orders", **params)
    _print_orders(orders)


def cmd_orders_show(args: argparse.Namespace) -> None:
    order = _get(f"/api/orders/{args.order_id}")
    _print_order_detail(order)


def cmd_price_set(args: argparse.Namespace) -> None:
    result = _put(f"/api/pricing/tiers/{args.tier_id}", {"unit_price": args.price})
    print(f"Updated tier #{result['tier_id']}  min_qty={result['min_quantity']}")
    print(f"  {result['old_price']:.2f} → {result['new_price']:.2f} €/unit")


def cmd_restock(args: argparse.Namespace) -> None:
    result = _post(f"/api/stock/{args.sp_id}/restock", {"quantity": args.quantity})
    print(f"Restocked: {result['material_name']}")
    print(f"  New quantity: {result['new_quantity']} units")


def cmd_day_advance(args: argparse.Namespace) -> None:
    result = _post("/api/day/advance")
    print(f"Day advanced: {result['previous_day']} → {result['current_day']}")
    if result.get("delivered_count", 0) > 0:
        print(f"  Delivered {result['delivered_count']} order(s): {result['orders_delivered']}")
    if result.get("shipped_count", 0) > 0:
        print(f"  Shipped   {result['shipped_count']} order(s): {result['orders_shipped']}")
    if result.get("delayed_count", 0) > 0:
        print(f"  DELAYED   {result['delayed_count']} order(s): {result['orders_delayed']}")
    if not result.get("delivered_count") and not result.get("shipped_count") and not result.get("delayed_count"):
        print("  No orders processed today.")


def cmd_day_current(args: argparse.Namespace) -> None:
    result = _get("/api/day/current")
    print(f"Supplier current day: {result['current_day']}")


def cmd_export(args: argparse.Namespace) -> None:
    data = _get("/api/export")
    out_file = getattr(args, "file", None) or f"supplier_export_day{data['sim_state']['current_day']}.json"
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
    print(f"Starting Supplier API on port {port}...")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "supplier_api.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload",
    ])


# ── Parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provider-cli",
        description="CLI for the Supplier API (provider)",
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    # catalog
    sub.add_parser("catalog", help="List products with pricing tiers")

    # stock
    sub.add_parser("stock", help="Show current inventory")

    # orders
    orders_p = sub.add_parser("orders", help="Manage purchase orders")
    orders_sub = orders_p.add_subparsers(dest="action", required=True)

    ol = orders_sub.add_parser("list", help="List orders")
    ol.add_argument("--status", default=None, help="Filter by status (pending/shipped/delivered)")

    os_ = orders_sub.add_parser("show", help="Show order detail")
    os_.add_argument("order_id", type=int, help="Order ID")

    # price
    price_p = sub.add_parser("price", help="Manage pricing tiers")
    price_sub = price_p.add_subparsers(dest="action", required=True)
    ps = price_sub.add_parser("set", help="Update a pricing tier")
    ps.add_argument("tier_id", type=int, help="Pricing tier ID")
    ps.add_argument("price", type=float, help="New unit price (€)")

    # restock
    rs = sub.add_parser("restock", help="Add to supplier stock")
    rs.add_argument("sp_id", type=int, help="SupplierProduct ID")
    rs.add_argument("quantity", type=int, help="Units to add")

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
    srv.add_argument("--port", type=int, default=8001, help="Port (default: 8001)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        ("catalog",): cmd_catalog,
        ("stock",): cmd_stock,
        ("orders", "list"): cmd_orders_list,
        ("orders", "show"): cmd_orders_show,
        ("price", "set"): cmd_price_set,
        ("restock",): cmd_restock,
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
