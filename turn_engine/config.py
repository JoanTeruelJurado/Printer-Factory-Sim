import json
from pathlib import Path


def load_config(path: str) -> dict:
    """Load turn engine configuration (apps, URLs, skills).

    Validates that the required top-level fields (retailers, manufacturer,
    providers) exist in the loaded JSON.

    Args:
        path: Filesystem path to the JSON config file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If a required key is missing.
    """
    config_path = Path(path)
    with config_path.open("r") as f:
        config = json.load(f)

    required_keys = ["retailers", "manufacturer", "providers"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Config missing required key: '{key}'")

    return config


def load_scenario(path: str) -> dict:
    """Load scenario file with events and demand signals.

    Args:
        path: Filesystem path to the scenario JSON file.

    Returns:
        Parsed scenario dictionary.

    Raises:
        FileNotFoundError: If the scenario file does not exist.
        ValueError: If the scenario is missing required fields.
    """
    scenario_path = Path(path)
    with scenario_path.open("r") as f:
        scenario = json.load(f)

    required_keys = ["scenario_name", "events"]
    for key in required_keys:
        if key not in scenario:
            raise ValueError(f"Scenario missing required key: '{key}'")

    return scenario


def todays_signal(day: int, scenario: dict) -> dict:
    """Extract today's market signal from the scenario.

    Checks which events are active for the current day (start_day <= day <=
    end_day) and compounds them.  Numeric modifiers (demand_modifier,
    supply_modifier, lead_time_modifier) are **multiplied** across all
    overlapping events so that concurrent stress stacks realistically.
    String hints (price_sensitivity) use last-writer-wins.
    base_demand is taken from the scenario top-level default, overridden by
    the last active event that defines it.

    Args:
        day: The current simulation day.
        scenario: A loaded scenario dictionary.

    Returns:
        A signal dict with base_demand, demand_modifier, supply_modifier,
        lead_time_modifier, price_sensitivity, and active_events.
    """
    base_demand = scenario.get("base_demand", {"mean": 5, "variance": 2})
    demand_modifier = 1.0
    supply_modifier = 1.0
    lead_time_modifier = 1.0
    price_sensitivity: str | None = None

    active_events: list[dict] = []
    for event in scenario.get("events", []):
        if event.get("start_day", 0) <= day <= event.get("end_day", float("inf")):
            active_events.append(event)

    for event in active_events:
        if "demand_modifier" in event:
            demand_modifier *= event["demand_modifier"]
        if "supply_modifier" in event:
            supply_modifier *= event["supply_modifier"]
        if "lead_time_modifier" in event:
            lead_time_modifier *= event["lead_time_modifier"]
        if "price_sensitivity" in event:
            price_sensitivity = event["price_sensitivity"]
        if "base_demand" in event:
            base_demand = event["base_demand"]

    return {
        "base_demand": base_demand,
        "demand_modifier": demand_modifier,
        "supply_modifier": supply_modifier,
        "lead_time_modifier": lead_time_modifier,
        "price_sensitivity": price_sensitivity,
        "active_events": active_events,
    }
