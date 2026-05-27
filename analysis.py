#!/usr/bin/env python3
"""Post-simulation analysis: reads metrics from all 3 databases and generates charts.

Usage:
    python analysis.py [--scenario LABEL] [--output-dir DIR]

Expects simulator.db, supplier.db, and retailer.db in the current directory.
"""

import argparse
import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


def query_db(db_path: str, sql: str) -> list[dict]:
    """Execute SQL and return list of dicts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_provider_metrics(db_path: str = "supplier.db") -> list[dict]:
    return query_db(db_path, "SELECT * FROM provider_metrics ORDER BY sim_day")


def load_manufacturer_metrics(db_path: str = "simulator.db") -> list[dict]:
    return query_db(db_path, "SELECT * FROM manufacturer_metrics ORDER BY sim_day")


def load_retailer_metrics(db_path: str = "retailer.db") -> list[dict]:
    return query_db(db_path, "SELECT * FROM retailer_metrics ORDER BY sim_day")


def load_scenario_events(scenario_path: str) -> list[dict]:
    """Load events from a scenario JSON file."""
    with open(scenario_path) as f:
        data = json.load(f)
    return data.get("events", [])


def plot_inventory(mfg_metrics: list, ret_metrics: list, output_dir: Path, label: str):
    """Chart 1: Inventory over time — parts, finished printers, retailer stock."""
    days_mfg = [m["sim_day"] for m in mfg_metrics]
    days_ret = [m["sim_day"] for m in ret_metrics]

    # Aggregate parts stock (sum of all materials)
    parts_stock = []
    for m in mfg_metrics:
        ps = json.loads(m["parts_stock_json"])
        parts_stock.append(sum(ps.values()))

    # Aggregate finished stock
    finished_stock = []
    for m in mfg_metrics:
        fs = json.loads(m["finished_stock_json"])
        finished_stock.append(sum(fs.values()))

    # Retailer stock
    retailer_stock = []
    for m in ret_metrics:
        rs = json.loads(m["printer_stock_json"])
        retailer_stock.append(sum(rs.values()))

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(days_mfg, parts_stock, "b-o", markersize=4, label="Parts stock (manufacturer)")
    ax.plot(days_mfg, finished_stock, "g-s", markersize=4, label="Finished printers (manufacturer)")
    if days_ret:
        ax.plot(days_ret, retailer_stock, "r-^", markersize=4, label="Printer stock (retailer)")
    ax.set_xlabel("Simulation Day")
    ax.set_ylabel("Units")
    ax.set_title(f"Inventory Over Time — {label}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"inventory_{label}.png", dpi=150)
    plt.close(fig)


def plot_prices(prov_metrics: list, mfg_metrics: list, ret_metrics: list,
                output_dir: Path, label: str):
    """Chart 2: Prices over time — provider, wholesale, retail."""
    days_prov = [m["sim_day"] for m in prov_metrics]
    days_mfg = [m["sim_day"] for m in mfg_metrics]
    days_ret = [m["sim_day"] for m in ret_metrics]

    # Provider: pick first product's price as representative
    prov_prices = []
    for m in prov_metrics:
        pp = json.loads(m["price_json"])
        prov_prices.append(list(pp.values())[0] if pp else 0)

    # Manufacturer wholesale: pick first product
    mfg_prices = []
    for m in mfg_metrics:
        wp = json.loads(m["wholesale_price_json"])
        mfg_prices.append(list(wp.values())[0] if wp else 0)

    # Retailer retail: pick first product
    ret_prices = []
    for m in ret_metrics:
        rp = json.loads(m["retail_price_json"])
        ret_prices.append(list(rp.values())[0] if rp else 0)

    fig, ax = plt.subplots(figsize=(12, 6))
    if days_prov:
        ax.plot(days_prov, prov_prices, "b-o", markersize=4, label="Provider (top tier)")
    if days_mfg:
        ax.plot(days_mfg, mfg_prices, "g-s", markersize=4, label="Manufacturer wholesale")
    if days_ret:
        ax.plot(days_ret, ret_prices, "r-^", markersize=4, label="Retailer retail")
    ax.set_xlabel("Simulation Day")
    ax.set_ylabel("Price (EUR)")
    ax.set_title(f"Prices Over Time — {label}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"prices_{label}.png", dpi=150)
    plt.close(fig)


def plot_fulfillment(ret_metrics: list, output_dir: Path, label: str):
    """Chart 3: Order fulfillment — daily bars."""
    days = [m["sim_day"] for m in ret_metrics]
    placed = [m["customer_orders_placed"] for m in ret_metrics]
    fulfilled = [m["customer_orders_fulfilled"] for m in ret_metrics]
    backordered = [m["customer_orders_backordered"] for m in ret_metrics]

    x = np.arange(len(days))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width, placed, width, label="Placed", color="steelblue")
    ax.bar(x, fulfilled, width, label="Fulfilled", color="seagreen")
    ax.bar(x + width, backordered, width, label="Backordered", color="indianred")
    ax.set_xlabel("Simulation Day")
    ax.set_ylabel("Orders")
    ax.set_title(f"Order Fulfillment — {label}")
    ax.set_xticks(x)
    ax.set_xticklabels(days)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(output_dir / f"fulfillment_{label}.png", dpi=150)
    plt.close(fig)


def plot_events_overlay(scenario_path: str, max_day: int, output_dir: Path, label: str):
    """Chart 4: Events overlay strip chart."""
    events = load_scenario_events(scenario_path)
    if not events:
        return

    colors = ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f"]
    fig, ax = plt.subplots(figsize=(12, 3))

    for i, event in enumerate(events):
        start = event.get("start_day", 1)
        end = event.get("end_day", max_day)
        color = colors[i % len(colors)]
        ax.barh(
            0.5 + i * 0.3, end - start + 1, left=start, height=0.25,
            color=color, alpha=0.7, label=event.get("name", f"Event {i+1}")
        )
        ax.text(
            start + (end - start + 1) / 2, 0.5 + i * 0.3,
            event.get("name", ""), ha="center", va="center", fontsize=8,
        )

    ax.set_xlim(0, max_day + 1)
    ax.set_xlabel("Simulation Day")
    ax.set_title(f"Scenario Events — {label}")
    ax.set_yticks([])
    ax.grid(True, alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(output_dir / f"events_{label}.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate simulation analysis charts")
    parser.add_argument("--scenario", default="run", help="Label for this scenario run")
    parser.add_argument("--scenario-file", default=None, help="Path to scenario JSON (for events overlay)")
    parser.add_argument("--output-dir", default="charts", help="Output directory for charts")
    parser.add_argument("--mfg-db", default="simulator.db", help="Manufacturer DB path")
    parser.add_argument("--supplier-db", default="supplier.db", help="Supplier DB path")
    parser.add_argument("--retailer-db", default="retailer.db", help="Retailer DB path")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"Loading metrics from databases...")

    try:
        prov_metrics = load_provider_metrics(args.supplier_db)
    except Exception as e:
        print(f"  [warn] Cannot load provider metrics: {e}")
        prov_metrics = []

    try:
        mfg_metrics = load_manufacturer_metrics(args.mfg_db)
    except Exception as e:
        print(f"  [warn] Cannot load manufacturer metrics: {e}")
        mfg_metrics = []

    try:
        ret_metrics = load_retailer_metrics(args.retailer_db)
    except Exception as e:
        print(f"  [warn] Cannot load retailer metrics: {e}")
        ret_metrics = []

    if not mfg_metrics and not ret_metrics:
        print("No metrics data found. Run a simulation first.")
        return

    print(f"  Provider: {len(prov_metrics)} days")
    print(f"  Manufacturer: {len(mfg_metrics)} days")
    print(f"  Retailer: {len(ret_metrics)} days")

    label = args.scenario

    if mfg_metrics or ret_metrics:
        plot_inventory(mfg_metrics, ret_metrics, output_dir, label)
        print(f"  -> inventory_{label}.png")

    if prov_metrics or mfg_metrics or ret_metrics:
        plot_prices(prov_metrics, mfg_metrics, ret_metrics, output_dir, label)
        print(f"  -> prices_{label}.png")

    if ret_metrics:
        plot_fulfillment(ret_metrics, output_dir, label)
        print(f"  -> fulfillment_{label}.png")

    if args.scenario_file:
        max_day = max(
            (m["sim_day"] for m in (mfg_metrics or ret_metrics or prov_metrics)),
            default=25,
        )
        plot_events_overlay(args.scenario_file, max_day, output_dir, label)
        print(f"  -> events_{label}.png")

    print(f"\nCharts saved to {output_dir}/")


if __name__ == "__main__":
    main()
