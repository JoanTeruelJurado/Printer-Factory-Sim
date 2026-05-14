#!/usr/bin/env python3
"""
manufacturer-cli — Command-line interface for the Factory API (manufacturer).

Usage:
  manufacturer-cli suppliers list                           List all suppliers
  manufacturer-cli suppliers catalog SUPPLIER_ID           Catalog for a supplier (by ID or name)
  manufacturer-cli stock                                    Show raw material inventory
  manufacturer-cli purchase list [--status STATUS]         List purchase orders
  manufacturer-cli purchase create                         Place a purchase order
      --supplier-id ID  (or --supplier NAME for partial match)
      --material-id ID  (or --material NAME for partial match)
      --qty QUANTITY
  manufacturer-cli day advance                              Advance simulation by one day
  manufacturer-cli day current                              Show current simulation day
  manufacturer-cli export [FILE]                            Export game state to JSON
  manufacturer-cli import FILE                              Import game state from JSON

Environment:
  FACTORY_API_URL   Base URL of the Factory API (default: http://localhost:8000)
  SUPPLIER_API_URL  Base URL of the Supplier API (default: http://localhost:8001)
"""

import argparse
import json
import os
import sys

import httpx

FACTORY_URL = os.getenv("FACTORY_API_URL", "http://localhost:8000")
SUPPLIER_URL = os.getenv("SUPPLIER_API_URL", "http://localhost:8001")
TIMEOUT = httpx.Timeout(10.0)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(base: str, path: str, **params) -> dict | list:
    url = f"{base}{path}"
    try:
        resp = httpx.get(url, params=params or None, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach API at {base}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def _post(base: str, path: str, payload: dict | None = None) -> dict | list:
    url = f"{base}{path}"
    try:
        resp = httpx.post(url, json=payload or {}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach API at {base}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def _fget(path: str, **params) -> dict | list:
    return _get(FACTORY_URL, path, **params)


def _fpost(path: str, payload: dict | None = None) -> dict | list:
    return _post(FACTORY_URL, path, payload)


def _sget(path: str, **params) -> dict | list:
    return _get(SUPPLIER_URL, path, **params)


# ── Formatters ─────────────────────────────────────────────────────────────────

def _separator(char: str = "─", width: int = 72) -> str:
    return char * width


def _print_suppliers(suppliers: list) -> None:
    print(_separator("═"))
    print(f"  {'ID':>4}  {'NAME':<32}  {'LEAD':>4}  {'RELIABILITY':>11}")
    print(_separator())
    for s in suppliers:
        print(f"  {s['id']:>4}  {s['name']:<32}  {s['lead_time_days']:>3}d  {s['reliability']:>11.2f}")
    print(_separator("═"))


def _print_catalog(catalog: dict) -> None:
    print(_separator("═"))
    print(f"  Supplier: [{catalog['supplier_id']}] {catalog['supplier_name']}")
    print(f"  Lead time: {catalog['lead_time_days']} day(s)  |  Reliability: {catalog['reliability']:.0%}")
    print(_separator())
    for item in catalog["catalog"]:
        current = item["base_unit_cost"] * item["daily_price_factor"]
        stock = item.get("stock", "?")
        print(f"  [{item['material_id']}] {item['material_name']}  current=€{current:.2f}  stock={stock}")
        for tier in item.get("pricing_tiers", []):
            effective = tier["unit_price"] * item["daily_price_factor"]
            print(f"      min_qty={tier['min_quantity']:>4}  €{effective:.2f}/u")
    print(_separator("═"))


def _print_inventory(items: list) -> None:
    print(_separator("═"))
    print(f"  {'MAT_ID':>6}  {'MATERIAL':<32}  {'QTY':>8}  {'RESERVED':>9}")
    print(_separator())
    for item in items:
        print(
            f"  {item['material_id']:>6}  {item['material_name']:<32}  "
            f"{item['quantity']:>8.0f}  {item['reserved_quantity']:>9.0f}"
        )
    print(_separator("═"))


def _print_purchase_orders(orders: list) -> None:
    print(_separator("═"))
    print(f"  {'ID':>4}  {'MATERIAL':<28}  {'QTY':>5}  {'STATUS':<10}  {'ISSUED':>6}  {'EXP.DEL':>7}  {'COST':>10}")
    print(_separator())
    for o in orders:
        print(
            f"  {o['po_id']:>4}  {o['material_name']:<28}  {o['quantity']:>5}  "
            f"{o['status']:<10}  day {o['issue_day']:>3}  day {o['expected_delivery_day']:>3}  "
            f"€{o['total_cost']:>9.2f}"
        )
    print(_separator("═"))
    print(f"  Total: {len(orders)} order(s)")


def _print_day_result(result: dict) -> None:
    data = result.get("data", result)
    wallet = data.get("wallet_balance", "N/A")
    print(f"Day {data.get('day', '?')} complete.")
    if isinstance(wallet, (int, float)):
        print(f"  Wallet:      €{wallet:,.2f}")
    print(f"  Produced:    {data.get('produced', 0)} unit(s)")
    print(f"  Deliveries:  {data.get('deliveries', 0)} purchase order(s) arrived")
    if data.get("delayed_deliveries", 0):
        print(f"  DELAYED:     {data['delayed_deliveries']} purchase order(s) delayed by supplier")
    print(f"  Demands:     {data.get('demands_created', 0)} new demand order(s)")
    if data.get("expired_demands", 0):
        print(f"  Expired:     {data['expired_demands']} demand(s) lost")
    if data.get("game_over"):
        print("  *** GAME OVER ***")


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def _resolve_supplier_id(args: argparse.Namespace) -> int:
    """Resolve supplier by --supplier-id or by partial name match from --supplier."""
    if hasattr(args, "supplier_id") and args.supplier_id is not None:
        return args.supplier_id
    if hasattr(args, "supplier") and args.supplier:
        suppliers = _sget("/suppliers")
        name_lower = args.supplier.lower()
        matches = [s for s in suppliers if name_lower in s["name"].lower()]
        if not matches:
            print(f"ERROR: No supplier matching '{args.supplier}'", file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            print(f"Ambiguous supplier '{args.supplier}': {[s['name'] for s in matches]}", file=sys.stderr)
            sys.exit(1)
        return matches[0]["id"]
    print("ERROR: provide --supplier-id or --supplier", file=sys.stderr)
    sys.exit(1)


def _resolve_material_id(supplier_id: int, args: argparse.Namespace) -> int:
    """Resolve material by --material-id or by partial name match from --material."""
    if hasattr(args, "material_id") and args.material_id is not None:
        return args.material_id
    if hasattr(args, "material") and args.material:
        catalog = _sget(f"/suppliers/{supplier_id}/catalog")
        name_lower = args.material.lower()
        matches = [item for item in catalog["catalog"] if name_lower in item["material_name"].lower()]
        if not matches:
            print(f"ERROR: No material matching '{args.material}' for this supplier", file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            print(f"Ambiguous material '{args.material}': {[m['material_name'] for m in matches]}", file=sys.stderr)
            sys.exit(1)
        return matches[0]["material_id"]
    print("ERROR: provide --material-id or --material", file=sys.stderr)
    sys.exit(1)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_suppliers_list(args: argparse.Namespace) -> None:
    suppliers = _sget("/suppliers")
    _print_suppliers(suppliers)


def cmd_suppliers_catalog(args: argparse.Namespace) -> None:
    supplier_id = _resolve_supplier_id(args)
    catalog = _fget(f"/api/suppliers/{supplier_id}/catalog")
    _print_catalog(catalog)


def cmd_stock(args: argparse.Namespace) -> None:
    items = _fget("/api/game/inventory")
    _print_inventory(items)


def cmd_purchase_list(args: argparse.Namespace) -> None:
    orders = _fget("/api/purchase-orders")
    if args.status:
        orders = [o for o in orders if o.get("status") == args.status]
    _print_purchase_orders(orders)


def cmd_purchase_create(args: argparse.Namespace) -> None:
    supplier_id = _resolve_supplier_id(args)
    material_id = _resolve_material_id(supplier_id, args)

    state = _fget("/api/game/state")
    if state.get("game_over"):
        print("ERROR: Game is over.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "supplier_id": supplier_id,
        "material_id": material_id,
        "quantity": args.qty,
    }
    order = _fpost("/api/purchase-orders", payload)
    print(_separator("═"))
    print(f"  Purchase order created!")
    print(_separator())
    print(f"  Order ID:          #{order['po_id']}")
    print(f"  Material:          {order['material_name']} (id={order['material_id']})")
    print(f"  Quantity:          {order['quantity']}")
    print(f"  Unit cost:         €{order['unit_cost']:.2f}")
    print(f"  Total cost:        €{order['total_cost']:.2f}")
    print(f"  Status:            {order['status']}")
    print(f"  Issued day:        {order['issue_day']}")
    print(f"  Expected delivery: day {order['expected_delivery_day']}")
    print(_separator("═"))


def cmd_day_advance(args: argparse.Namespace) -> None:
    result = _fpost("/api/game/advance-day")
    _print_day_result(result)


def cmd_day_current(args: argparse.Namespace) -> None:
    state = _fget("/api/game/state")
    print(f"Manufacturer current day: {state['current_day']}")
    print(f"  Wallet: €{state['wallet_balance']:,.2f}")
    if state.get("game_over"):
        print("  *** GAME OVER ***")


def cmd_export(args: argparse.Namespace) -> None:
    data = _fget("/api/game/export")
    day = data.get("game_state", {}).get("current_day", "?")
    out_file = getattr(args, "file", None) or f"factory_export_day{day}.json"
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported to {out_file}")


def cmd_import(args: argparse.Namespace) -> None:
    with open(args.file) as f:
        payload = json.load(f)
    result = _fpost("/api/game/import", payload)
    print(result.get("message", str(result)))


# ── Parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manufacturer-cli",
        description="CLI for the Factory API (manufacturer)",
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    # suppliers
    sup_p = sub.add_parser("suppliers", help="Supplier commands")
    sup_sub = sup_p.add_subparsers(dest="action", required=True)

    sup_sub.add_parser("list", help="List all suppliers")

    cat = sup_sub.add_parser("catalog", help="Show supplier catalog")
    cat_id = cat.add_mutually_exclusive_group(required=True)
    cat_id.add_argument("--supplier-id", type=int, dest="supplier_id", help="Supplier ID")
    cat_id.add_argument("--supplier", type=str, help="Supplier name (partial match)")

    # stock
    sub.add_parser("stock", help="Show raw material inventory")

    # purchase
    pur_p = sub.add_parser("purchase", help="Purchase order commands")
    pur_sub = pur_p.add_subparsers(dest="action", required=True)

    pl = pur_sub.add_parser("list", help="List purchase orders")
    pl.add_argument("--status", default=None, help="Filter by status")

    pc = pur_sub.add_parser("create", help="Place a purchase order")
    sid_grp = pc.add_mutually_exclusive_group(required=True)
    sid_grp.add_argument("--supplier-id", type=int, dest="supplier_id", help="Supplier ID")
    sid_grp.add_argument("--supplier", type=str, help="Supplier name (partial match)")
    mid_grp = pc.add_mutually_exclusive_group(required=True)
    mid_grp.add_argument("--material-id", type=int, dest="material_id", help="Material ID")
    mid_grp.add_argument("--material", type=str, help="Material name (partial match)")
    pc.add_argument("--qty", type=int, required=True, help="Quantity to order")

    # day
    day_p = sub.add_parser("day", help="Simulation day commands")
    day_sub = day_p.add_subparsers(dest="action", required=True)
    day_sub.add_parser("advance", help="Advance one simulation day")
    day_sub.add_parser("current", help="Show current simulation day")

    # export
    exp = sub.add_parser("export", help="Export game state to JSON")
    exp.add_argument("file", nargs="?", default=None, help="Output file (default: auto-named)")

    # import
    imp = sub.add_parser("import", help="Import game state from JSON")
    imp.add_argument("file", help="JSON file to import")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        ("suppliers", "list"): cmd_suppliers_list,
        ("suppliers", "catalog"): cmd_suppliers_catalog,
        ("stock",): cmd_stock,
        ("purchase", "list"): cmd_purchase_list,
        ("purchase", "create"): cmd_purchase_create,
        ("day", "advance"): cmd_day_advance,
        ("day", "current"): cmd_day_current,
        ("export",): cmd_export,
        ("import",): cmd_import,
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
