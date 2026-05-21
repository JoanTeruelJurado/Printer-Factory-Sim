"""
Retailer configuration loader.

Reads retailer settings from a JSON file (path configurable via
RETAILER_CONFIG env var, default "retailer_config.json").
"""

import json
import os
from typing import Any, Dict

_DEFAULT_CONFIG: Dict[str, Any] = {
    "retailer": {
        "name": "PrinterWorld",
        "port": 8003,
        "manufacturer": {
            "name": "Factory",
            "url": "http://localhost:8002",
        },
        "markup_pct": 30,
    }
}


def load_retailer_config(path: str | None = None) -> Dict[str, Any]:
    """Load retailer configuration from a JSON file.

    Resolution order:
      1. Explicit *path* argument
      2. RETAILER_CONFIG environment variable
      3. "retailer_config.json" in the current working directory

    Returns the default config if the file does not exist.
    """
    if path is None:
        path = os.getenv("RETAILER_CONFIG", "retailer_config.json")

    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return _DEFAULT_CONFIG
