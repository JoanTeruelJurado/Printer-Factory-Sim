#!/usr/bin/env python3
"""Turn engine entry point: orchestrates simulated days across all apps."""

import sys

from turn_engine.config import load_config, load_scenario
from turn_engine.engine import run_day

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python turn_engine.py <config.json> <scenario.json> <num_days>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    scenario = load_scenario(sys.argv[2])
    days = int(sys.argv[3])

    print(f"Turn Engine: {scenario.get('scenario_name', 'unknown')} for {days} day(s)")
    print(f"Retailers: {[r['name'] for r in config['retailers']]}")
    print(f"Manufacturer: {config['manufacturer']['name']}")
    print(f"Providers: {[p['name'] for p in config['providers']]}")

    for day in range(1, days + 1):
        run_day(day, config, scenario)

    print(f"\n{'='*60}")
    print(f"  Simulation complete: {days} day(s)")
    print(f"{'='*60}")
