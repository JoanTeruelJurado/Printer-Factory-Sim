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


def _put(base: str, path: str, payload: dict | None = None) -> dict | list:
    url = f"{base}{path}"
    try:
        resp = httpx.put(url, json=payload or {}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach API at {base}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def _fput(path: str, payload: dict | None = None) -> dict | list:
    return _put(FACTORY_URL, path, payload)


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


def _print_sales_orders(orders: list) -> None:
    print(_separator("═"))
    print(f"  {'ID':>4}  {'RETAILER':<20}  {'PRODUCT':<16}  {'QTY':>5}  {'STATUS':<10}  {'ORDERED':>7}  {'TOTAL':>10}")
    print(_separator())
    for o in orders:
        print(
            f"  {o['id']:>4}  {o['retailer_name']:<20}  {o['product_name']:<16}  "
            f"{o['quantity']:>5}  {o['status']:<10}  day {o['ordered_day']:>3}  "
            f"€{o['total_price']:>9.2f}"
        )
    print(_separator("═"))
    print(f"  Total: {len(orders)} order(s)")


def _print_sales_order_detail(o: dict) -> None:
    print(_separator("═"))
    print(f"  Sales Order #{o['id']}")
    print(_separator())
    print(f"  Retailer:      {o['retailer_name']}")
    print(f"  Product:       {o['product_name']} (id={o['product_id']})")
    print(f"  Quantity:      {o['quantity']}")
    print(f"  Unit price:    €{o['unit_price']:.2f}")
    print(f"  Total price:   €{o['total_price']:.2f}")
    print(f"  Status:        {o['status']}")
    print(f"  Ordered day:   {o['ordered_day']}")
    if o.get('released_day') is not None:
        print(f"  Released day:  {o['released_day']}")
    if o.get('completed_day') is not None:
        print(f"  Completed day: {o['completed_day']}")
    if o.get('shipped_day') is not None:
        print(f"  Shipped day:   {o['shipped_day']}")
    if o.get('delivered_day') is not None:
        print(f"  Delivered day: {o['delivered_day']}")
    print(_separator("═"))


def _print_prices(products: list) -> None:
    print(_separator("═"))
    print(f"  {'ID':>4}  {'PRODUCT':<32}  {'SELL PRICE':>12}  {'ASSEMBLY (h)':>12}")
    print(_separator())
    for p in products:
        price_str = f"€{p['sell_price']:.2f}" if p.get('sell_price') is not None else "N/A"
        print(f"  {p['product_id']:>4}  {p['product_name']:<32}  {price_str:>12}  {p['assembly_time_hours']:>12.1f}")
    print(_separator("═"))


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


def cmd_sales_orders(args: argparse.Namespace) -> None:
    params = {}
    if args.status:
        params["status"] = args.status
    orders = _fget("/api/orders", **params)
    _print_sales_orders(orders)


def cmd_sales_order(args: argparse.Namespace) -> None:
    order = _fget(f"/api/orders/{args.order_id}")
    _print_sales_order_detail(order)


def cmd_production_release(args: argparse.Namespace) -> None:
    result = _fput(f"/api/orders/{args.order_id}/release")
    print(_separator("═"))
    print(f"  Sales order #{result['id']} released to production")
    print(_separator())
    print(f"  Retailer:    {result['retailer_name']}")
    print(f"  Product:     {result['product_name']}")
    print(f"  Quantity:    {result['quantity']}")
    print(f"  Status:      {result['status']}")
    print(f"  Released day: {result.get('released_day', 'N/A')}")
    print(_separator("═"))


def cmd_production_status(args: argparse.Namespace) -> None:
    data = _fget("/api/production/status")
    print(_separator("═"))
    print("  PRODUCTION STATUS")
    print(_separator())
    if data["manufacturing_orders"]:
        print("  Manufacturing Orders (released):")
        for mo in data["manufacturing_orders"]:
            print(f"    MO #{mo['id']:>4}  {mo['product_name']:<20}  qty={mo['quantity']}  remaining={mo['remaining_qty']}")
    else:
        print("  Manufacturing Orders: (none released)")
    print()
    if data["sales_orders"]:
        print("  Sales Orders (released):")
        for so in data["sales_orders"]:
            print(f"    SO #{so['id']:>4}  {so['retailer_name']:<16}  {so['product_name']:<20}  qty={so['quantity']}")
    else:
        print("  Sales Orders: (none released)")
    print(_separator())
    print(f"  Total released units: {data['total_released_units']}")
    print(_separator("═"))


def cmd_capacity(args: argparse.Namespace) -> None:
    data = _fget("/api/capacity")
    print(_separator("═"))
    print("  CAPACITY")
    print(_separator())
    print(f"  Daily production capacity: {data['daily_production_capacity']} units/day")
    print(f"  Released MO units:         {data['released_mo_units']}")
    print(f"  Released sales units:      {data['released_sales_units']}")
    print(f"  Total queued units:        {data['total_queued_units']}")
    print(f"  Warehouse capacity:        {data['warehouse_capacity']}")
    print(_separator("═"))


def cmd_price_list(args: argparse.Namespace) -> None:
    products = _fget("/api/game/products")
    _print_prices(products)


def cmd_price_set(args: argparse.Namespace) -> None:
    # Look up product by name
    products = _fget("/api/game/products")
    name_lower = args.model.lower()
    matches = [p for p in products if name_lower in p["product_name"].lower()]
    if not matches:
        print(f"ERROR: No product matching '{args.model}'", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"Ambiguous product '{args.model}': {[p['product_name'] for p in matches]}", file=sys.stderr)
        sys.exit(1)
    product_id = matches[0]["product_id"]
    result = _fput(f"/api/game/products/{product_id}/price", {"sell_price": args.price})
    print(f"Updated {result['product_name']}: €{result['old_price']:.2f} → €{result['new_price']:.2f}")


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

    # production
    prod_p = sub.add_parser("production", help="Production commands")
    prod_sub = prod_p.add_subparsers(dest="action", required=True)

    prod_rel = prod_sub.add_parser("release", help="Release a sales order to production")
    prod_rel.add_argument("order_id", type=int, help="Sales order ID")

    prod_sub.add_parser("status", help="Show released/in-progress orders")

    # capacity
    sub.add_parser("capacity", help="Show daily capacity and utilization")

    # sales
    sal_p = sub.add_parser("sales", help="Sales order commands")
    sal_sub = sal_p.add_subparsers(dest="action", required=True)

    sol = sal_sub.add_parser("orders", help="List sales orders")
    sol.add_argument("--status", default=None, help="Filter by status")

    sod = sal_sub.add_parser("order", help="Show sales order detail")
    sod.add_argument("order_id", type=int, help="Sales order ID")

    # price
    pri_p = sub.add_parser("price", help="Product pricing commands")
    pri_sub = pri_p.add_subparsers(dest="action", required=True)

    pri_sub.add_parser("list", help="Show wholesale prices for finished products")

    pset = pri_sub.add_parser("set", help="Set wholesale price for a product")
    pset.add_argument("model", type=str, help="Product name (partial match)")
    pset.add_argument("price", type=float, help="New sell price")

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
        ("production", "release"): cmd_production_release,
        ("production", "status"): cmd_production_status,
        ("capacity",): cmd_capacity,
        ("sales", "orders"): cmd_sales_orders,
        ("sales", "order"): cmd_sales_order,
        ("price", "list"): cmd_price_list,
        ("price", "set"): cmd_price_set,
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
