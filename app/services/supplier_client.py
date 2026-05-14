"""
HTTP client for the Supplier API.

All factory services use this module to communicate with the
standalone Supplier API (port 8001) via synchronous HTTP calls.

Base URL is read from the SUPPLIER_API_URL environment variable,
defaulting to http://localhost:8001.
"""

import json
import os
from pathlib import Path

import httpx

# Load base URL from manufacturer_config.json if present; env var overrides.
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "manufacturer_config.json"
_config_url: str | None = None
if _CONFIG_PATH.exists():
    try:
        _cfg = json.loads(_CONFIG_PATH.read_text())
        _providers = _cfg.get("manufacturer", {}).get("providers", [])
        if _providers:
            _config_url = _providers[0]["url"]
    except Exception:
        pass

SUPPLIER_API_URL: str = os.getenv("SUPPLIER_API_URL", _config_url or "http://localhost:8001")

# Shared timeout (seconds) for all requests
_TIMEOUT = httpx.Timeout(10.0)


class SupplierAPIError(Exception):
    """Raised when the Supplier API is unreachable or returns an error."""


def _get(path: str, **params) -> httpx.Response:
    """Perform a GET request against the Supplier API."""
    url = f"{SUPPLIER_API_URL}{path}"
    try:
        resp = httpx.get(url, params=params if params else None, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError as exc:
        raise SupplierAPIError(
            f"Cannot reach Supplier API at {SUPPLIER_API_URL}: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SupplierAPIError(
            f"Supplier API returned {exc.response.status_code} for GET {path}: "
            f"{exc.response.text}"
        ) from exc


def _post(path: str, payload: dict) -> httpx.Response:
    """Perform a POST request against the Supplier API."""
    url = f"{SUPPLIER_API_URL}{path}"
    try:
        resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError as exc:
        raise SupplierAPIError(
            f"Cannot reach Supplier API at {SUPPLIER_API_URL}: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SupplierAPIError(
            f"Supplier API returned {exc.response.status_code} for POST {path}: "
            f"{exc.response.text}"
        ) from exc


def _delete(path: str) -> httpx.Response:
    """Perform a DELETE request against the Supplier API."""
    url = f"{SUPPLIER_API_URL}{path}"
    try:
        resp = httpx.delete(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError as exc:
        raise SupplierAPIError(
            f"Cannot reach Supplier API at {SUPPLIER_API_URL}: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SupplierAPIError(
            f"Supplier API returned {exc.response.status_code} for DELETE {path}: "
            f"{exc.response.text}"
        ) from exc


def _put(path: str, payload: dict) -> httpx.Response:
    """Perform a PUT request against the Supplier API."""
    url = f"{SUPPLIER_API_URL}{path}"
    try:
        resp = httpx.put(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError as exc:
        raise SupplierAPIError(
            f"Cannot reach Supplier API at {SUPPLIER_API_URL}: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise SupplierAPIError(
            f"Supplier API returned {exc.response.status_code} for PUT {path}: "
            f"{exc.response.text}"
        ) from exc


# ── Public API ─────────────────────────────────────────────────────────────────

def get_suppliers() -> list[dict]:
    """Return a list of all suppliers from the Supplier API."""
    return _get("/suppliers").json()


def get_catalog(supplier_id: int) -> dict:
    """Return the catalog (with current prices) for the given supplier."""
    return _get(f"/suppliers/{supplier_id}/catalog").json()


def get_pricing(supplier_id: int, material_id: int, quantity: int | None = None) -> dict:
    """Return pricing details for a specific material from a supplier.

    If *quantity* is provided, the returned price reflects the applicable
    volume-discount tier (as computed by the Supplier API).
    """
    params = {"quantity": quantity} if quantity is not None else {}
    return _get(f"/suppliers/{supplier_id}/pricing/{material_id}", **params).json()


def create_order(payload: dict) -> dict:
    """Create a purchase order in the Supplier API. Returns the created order dict."""
    return _post("/orders", payload).json()


def get_orders() -> list[dict]:
    """Return all purchase orders recorded in the Supplier API."""
    return _get("/orders").json()


def get_due_orders(day: int) -> list[dict]:
    """Return pending orders with expected_delivery_day <= day."""
    return _get("/orders/due", day=day).json()


def deliver_order(order_id: int, actual_delivery_day: int) -> dict:
    """Mark a purchase order as delivered. Returns the updated order dict."""
    return _put(f"/orders/{order_id}/deliver", {"actual_delivery_day": actual_delivery_day}).json()


def advance_supplier_day() -> dict:
    """Advance the supplier's simulation day (ships pending orders, delivers due ones)."""
    return _post("/api/day/advance", {}).json()


def fluctuate_prices() -> None:
    """Trigger ±10% price fluctuation on all supplier products."""
    _post("/prices/fluctuate", {})


def reset_orders() -> int:
    """Delete all purchase orders in the Supplier API. Returns count deleted."""
    return _delete("/orders").json().get("deleted", 0)
