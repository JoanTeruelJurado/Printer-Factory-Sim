"""Turn engine orchestration: runs one simulated day across all apps."""

import json
import subprocess
from pathlib import Path

import httpx

from turn_engine.config import todays_signal
from turn_engine.demand import generate_customer_demand

TIMEOUT = httpx.Timeout(15.0)


def generate_customer_orders(retailer_url: str, signal: dict, scenario: dict) -> int:
    """Fetch retailer catalog, generate demand, POST each order.

    Returns number of orders created.
    """
    try:
        catalog_resp = httpx.get(f"{retailer_url}/api/catalog", timeout=TIMEOUT)
        catalog_resp.raise_for_status()
        catalog = catalog_resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        print(f"  [warn] Cannot reach retailer at {retailer_url}: {e}")
        return 0

    # Build retailer_prices from catalog
    retailer_prices = {}
    for item in catalog.get("items", catalog if isinstance(catalog, list) else []):
        name = item.get("model_name", item.get("model", ""))
        price = item.get("retail_price", 0)
        if name and price:
            retailer_prices[name] = price

    base_price = scenario.get("base_price", 400.0)

    orders = generate_customer_demand(
        day=signal.get("day", 1),
        signal=signal,
        retailer_prices=retailer_prices,
        base_price=base_price,
    )

    created = 0
    for model, qty in orders:
        try:
            resp = httpx.post(
                f"{retailer_url}/api/orders",
                json={"customer": "auto", "model": model, "quantity": qty},
                timeout=TIMEOUT,
            )
            if resp.status_code in (200, 201):
                created += 1
        except (httpx.ConnectError, httpx.HTTPStatusError):
            pass

    return created


def _write_log(day: int, role: str, content: str) -> Path:
    """Write agent output to logs/day-NNN-role.log."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"day-{day:03d}-{role}.log"
    log_file.write_text(content, encoding="utf-8")
    return log_file


def fetch_manufacturer_context(url: str) -> dict:
    """Fetch full game state from manufacturer's agent context endpoint."""
    try:
        resp = httpx.get(f"{url}/api/agent/context", timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        print(f"  [warn] Cannot fetch manufacturer context: {e}")
        return {}


def build_agent_context(day: int, signal: dict, config: dict) -> dict:
    """Build rich context dict for agent decision-making."""
    context: dict = {"day": day, "signal": signal}

    # Fetch manufacturer state
    mfg_url = config["manufacturer"]["url"]
    mfg_state = fetch_manufacturer_context(mfg_url)
    if mfg_state:
        context["manufacturer"] = mfg_state

    return context


def run_agent_or_stub(
    role: str,
    skill_path: str | None,
    context: str,
    cwd: str,
    day: int = 0,
) -> str:
    """Invoke claude --print for roles with skill files, or log a stub.

    Captures agent output to logs/day-NNN-role.log.
    """
    if skill_path is None:
        msg = f"[stub] {role} would make decisions here"
        print(f"  {msg}")
        _write_log(day, role, msg)
        return msg

    prompt = f"""Read the skill file at {skill_path}.
Today's context: {context}
Execute your daily decisions following the skill's decision framework.
Do NOT advance the day — the turn engine does that."""

    try:
        result = subprocess.run(
            ["claude", "--print", "--prompt", prompt],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=180,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n--- stderr ---\n{result.stderr}"
        print(f"  [{role}] {output[:200]}...")
        _write_log(day, role, output)
        return output
    except subprocess.TimeoutExpired:
        msg = f"[{role}] TIMEOUT after 180s"
        print(f"  {msg}")
        _write_log(day, role, msg)
        return msg
    except FileNotFoundError:
        msg = f"[{role}] claude command not found, skipping"
        print(f"  {msg}")
        _write_log(day, role, msg)
        return msg


def advance_all(urls: list[str]) -> dict[str, dict]:
    """Advance all apps by calling POST /api/day/advance on each."""
    results = {}
    for url in urls:
        try:
            resp = httpx.post(f"{url}/api/day/advance", timeout=TIMEOUT)
            resp.raise_for_status()
            results[url] = resp.json()
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            print(f"  [warn] Failed to advance {url}: {e}")
            results[url] = {"error": str(e)}
    return results


def run_day(day: int, config: dict, scenario: dict) -> dict:
    """Run one complete simulated day."""
    signal = todays_signal(day, scenario)
    signal["day"] = day

    print(f"\n{'='*60}")
    print(f"  DAY {day}")
    print(f"  Signal: demand_modifier={signal.get('demand_modifier', 1.0)}")
    print(f"{'='*60}")

    # 1. Inject customer demand at each retailer
    total_demand = 0
    for retailer in config["retailers"]:
        count = generate_customer_orders(retailer["url"], signal, scenario)
        total_demand += count
        print(f"  Injected {count} customer orders at {retailer['name']}")

    # 2. Build rich context for agents
    agent_context = build_agent_context(day, signal, config)
    context_str = json.dumps(agent_context, default=str)

    # 3. Retailer decisions
    for retailer in config["retailers"]:
        run_agent_or_stub(
            f"retailer-{retailer['name']}",
            retailer.get("skill"),
            context_str,
            retailer.get("path", "."),
            day=day,
        )

    # 4. Manufacturer decisions
    mfg = config["manufacturer"]
    run_agent_or_stub(
        "manufacturer",
        mfg.get("skill"),
        context_str,
        mfg.get("path", "."),
        day=day,
    )

    # 5. Provider decisions
    for provider in config["providers"]:
        run_agent_or_stub(
            f"provider-{provider['name']}",
            provider.get("skill"),
            context_str,
            provider.get("path", "."),
            day=day,
        )

    # 6. Advance all apps
    all_urls = (
        [r["url"] for r in config["retailers"]]
        + [mfg["url"]]
        + [p["url"] for p in config["providers"]]
    )
    advance_results = advance_all(all_urls)

    print(f"  Day {day} complete. Advanced {len(advance_results)} app(s).")

    return {
        "day": day,
        "demand_injected": total_demand,
        "advance_results": advance_results,
    }
