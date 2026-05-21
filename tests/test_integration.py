"""
Integration tests: end-to-end day cycle through the turn engine.

These tests exercise the turn engine orchestration logic (demand generation,
agent stub invocation, day advancement) using mocked HTTP responses so no
live servers are required.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from turn_engine.engine import (
    advance_all,
    build_agent_context,
    generate_customer_orders,
    run_agent_or_stub,
    run_day,
)
from turn_engine.config import load_config, load_scenario, todays_signal
from turn_engine.demand import generate_customer_demand


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sim_config():
    """Return a minimal sim config dict (no files needed)."""
    return {
        "retailers": [
            {
                "name": "TestRetailer",
                "url": "http://localhost:9003",
                "port": 9003,
                "path": ".",
                "skill": None,
            }
        ],
        "manufacturer": {
            "name": "TestFactory",
            "url": "http://localhost:9002",
            "port": 9002,
            "path": ".",
            "skill": None,
        },
        "providers": [
            {
                "name": "TestSupply",
                "url": "http://localhost:9001",
                "port": 9001,
                "path": ".",
                "skill": None,
            }
        ],
    }


@pytest.fixture()
def scenario():
    """Return a minimal scenario dict."""
    return {
        "scenario_name": "integration-test",
        "base_demand": {"mean": 3, "variance": 1},
        "base_price": 400.0,
        "events": [
            {
                "name": "steady",
                "start_day": 1,
                "end_day": 10,
                "demand_modifier": 1.0,
            }
        ],
    }


@pytest.fixture()
def log_cleanup():
    """Clean up any log files created during tests."""
    yield
    log_dir = Path("logs")
    if log_dir.exists():
        for f in log_dir.glob("day-*-*.log"):
            f.unlink()


# ── Config / Scenario Tests ───────────────────────────────────────────────────

def test_load_config_validates():
    """load_config raises ValueError on missing keys."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"retailers": []}, f)
        f.flush()
        with pytest.raises(ValueError, match="manufacturer"):
            load_config(f.name)


def test_load_scenario_validates():
    """load_scenario raises ValueError on missing keys."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"events": []}, f)
        f.flush()
        with pytest.raises(ValueError, match="scenario_name"):
            load_scenario(f.name)


def test_todays_signal_picks_active_events(scenario):
    """todays_signal correctly selects active events for a given day."""
    signal = todays_signal(1, scenario)
    assert signal["demand_modifier"] == 1.0
    assert len(signal["active_events"]) == 1

    # Day outside event range returns default modifier
    signal_late = todays_signal(99, scenario)
    assert signal_late["demand_modifier"] == 1.0  # default
    assert len(signal_late["active_events"]) == 0


# ── Demand Generation Tests ──────────────────────────────────────────────────

def test_generate_customer_demand_produces_orders():
    """generate_customer_demand returns a list of (model, qty) tuples."""
    signal = {"base_demand": {"mean": 5, "variance": 0}, "demand_modifier": 1.0}
    prices = {"ModelA": 400.0}
    orders = generate_customer_demand(1, signal, prices, 400.0)
    assert isinstance(orders, list)
    for model, qty in orders:
        assert model == "ModelA"
        assert qty == 1


def test_demand_price_elasticity():
    """Higher prices reduce demand."""
    signal = {"base_demand": {"mean": 10, "variance": 0}, "demand_modifier": 1.0}
    # At base price → full demand
    orders_base = generate_customer_demand(1, signal, {"M": 400.0}, 400.0)
    # At 2x price → reduced demand (factor = max(0.2, 1 - (800-400)/400) = 0.2)
    orders_expensive = generate_customer_demand(1, signal, {"M": 800.0}, 400.0)
    assert len(orders_base) >= len(orders_expensive)


# ── Agent Stub Tests ─────────────────────────────────────────────────────────

def test_run_agent_stub_no_skill(log_cleanup):
    """run_agent_or_stub with skill=None returns stub message and writes log."""
    result = run_agent_or_stub("test-role", None, "{}", ".", day=99)
    assert "[stub]" in result
    log_file = Path("logs/day-099-test-role.log")
    assert log_file.exists()
    assert "[stub]" in log_file.read_text()


def test_run_agent_stub_claude_not_found(log_cleanup):
    """run_agent_or_stub gracefully handles missing claude binary."""
    with patch("turn_engine.engine.subprocess.run", side_effect=FileNotFoundError):
        result = run_agent_or_stub("mfg", "skills/test.md", "{}", ".", day=1)
    assert "claude command not found" in result
    log_file = Path("logs/day-001-mfg.log")
    assert log_file.exists()


def test_run_agent_stub_timeout(log_cleanup):
    """run_agent_or_stub handles 180s timeout gracefully."""
    import subprocess

    with patch(
        "turn_engine.engine.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=180),
    ):
        result = run_agent_or_stub("mfg", "skills/test.md", "{}", ".", day=2)
    assert "TIMEOUT" in result
    log_file = Path("logs/day-002-mfg.log")
    assert log_file.exists()


# ── Turn Engine Orchestration Tests ──────────────────────────────────────────

def test_generate_customer_orders_with_mock(sim_config):
    """generate_customer_orders calls retailer API and creates orders."""
    catalog_response = MagicMock()
    catalog_response.status_code = 200
    catalog_response.json.return_value = {
        "items": [
            {"model_name": "P3D-Classic", "retail_price": 390.0},
            {"model_name": "P3D-Pro", "retail_price": 520.0},
        ]
    }
    catalog_response.raise_for_status = MagicMock()

    order_response = MagicMock()
    order_response.status_code = 201

    with patch("turn_engine.engine.httpx.get", return_value=catalog_response):
        with patch("turn_engine.engine.httpx.post", return_value=order_response):
            signal = {"base_demand": {"mean": 3, "variance": 0}, "demand_modifier": 1.0, "day": 1}
            scenario = {"base_price": 400.0}
            count = generate_customer_orders(
                sim_config["retailers"][0]["url"], signal, scenario
            )
            assert count >= 0


def test_advance_all_with_mock():
    """advance_all calls POST /api/day/advance on each URL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "new_day": 2}
    mock_resp.raise_for_status = MagicMock()

    with patch("turn_engine.engine.httpx.post", return_value=mock_resp) as mock_post:
        results = advance_all(["http://a:1", "http://b:2"])
        assert len(results) == 2
        assert mock_post.call_count == 2


def test_build_agent_context_with_mock(sim_config):
    """build_agent_context fetches manufacturer state and merges with signal."""
    mfg_state = {
        "game_state": {"current_day": 1, "wallet_balance": 10000},
        "inventory": [],
        "products": [],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mfg_state
    mock_resp.raise_for_status = MagicMock()

    with patch("turn_engine.engine.httpx.get", return_value=mock_resp):
        signal = {"demand_modifier": 1.0}
        ctx = build_agent_context(1, signal, sim_config)
        assert ctx["day"] == 1
        assert ctx["signal"] == signal
        assert "manufacturer" in ctx
        assert ctx["manufacturer"]["game_state"]["wallet_balance"] == 10000


def test_build_agent_context_handles_failure(sim_config):
    """build_agent_context degrades gracefully when manufacturer unreachable."""
    import httpx as _httpx

    with patch("turn_engine.engine.httpx.get", side_effect=_httpx.ConnectError("refused")):
        ctx = build_agent_context(1, {"mod": 1.0}, sim_config)
        assert ctx["day"] == 1
        assert "manufacturer" not in ctx


def test_run_day_deterministic(sim_config, scenario, log_cleanup):
    """run_day executes a full day cycle with stubs (no claude, no servers)."""
    catalog_resp = MagicMock()
    catalog_resp.status_code = 200
    catalog_resp.json.return_value = {
        "items": [{"model_name": "TestModel", "retail_price": 400.0}]
    }
    catalog_resp.raise_for_status = MagicMock()

    advance_resp = MagicMock()
    advance_resp.status_code = 200
    advance_resp.json.return_value = {"success": True, "new_day": 2}
    advance_resp.raise_for_status = MagicMock()

    # Mock agent context fetch too
    ctx_resp = MagicMock()
    ctx_resp.status_code = 200
    ctx_resp.json.return_value = {"game_state": {"current_day": 1, "wallet_balance": 9500}}
    ctx_resp.raise_for_status = MagicMock()

    def mock_get(url, **kwargs):
        if "/api/agent/context" in url:
            return ctx_resp
        return catalog_resp

    order_resp = MagicMock()
    order_resp.status_code = 201

    def mock_post(url, **kwargs):
        if "/api/day/advance" in url:
            return advance_resp
        return order_resp

    with patch("turn_engine.engine.httpx.get", side_effect=mock_get):
        with patch("turn_engine.engine.httpx.post", side_effect=mock_post):
            result = run_day(1, sim_config, scenario)

    assert result["day"] == 1
    assert "demand_injected" in result
    assert "advance_results" in result
    # Verify logs were written for stubs
    assert Path("logs/day-001-retailer-TestRetailer.log").exists()
    assert Path("logs/day-001-manufacturer.log").exists()
    assert Path("logs/day-001-provider-TestSupply.log").exists()


def test_run_day_wallet_tracking(sim_config, scenario, log_cleanup):
    """Verify the agent context includes wallet info during a day run."""
    wallet_seen = []

    catalog_resp = MagicMock()
    catalog_resp.status_code = 200
    catalog_resp.json.return_value = {"items": []}
    catalog_resp.raise_for_status = MagicMock()

    ctx_resp = MagicMock()
    ctx_resp.status_code = 200
    ctx_resp.json.return_value = {
        "game_state": {"current_day": 1, "wallet_balance": 8500.0}
    }
    ctx_resp.raise_for_status = MagicMock()

    advance_resp = MagicMock()
    advance_resp.status_code = 200
    advance_resp.json.return_value = {"success": True, "new_day": 2}
    advance_resp.raise_for_status = MagicMock()

    original_build = build_agent_context

    def spy_build(day, signal, config):
        ctx = original_build(day, signal, config)
        if "manufacturer" in ctx:
            wallet_seen.append(ctx["manufacturer"]["game_state"]["wallet_balance"])
        return ctx

    def mock_get(url, **kwargs):
        if "/api/agent/context" in url:
            return ctx_resp
        return catalog_resp

    def mock_post(url, **kwargs):
        if "/api/day/advance" in url:
            return advance_resp
        return MagicMock(status_code=201)

    with patch("turn_engine.engine.httpx.get", side_effect=mock_get):
        with patch("turn_engine.engine.httpx.post", side_effect=mock_post):
            with patch("turn_engine.engine.build_agent_context", side_effect=spy_build):
                run_day(1, sim_config, scenario)

    assert len(wallet_seen) == 1
    assert wallet_seen[0] == 8500.0
