from __future__ import annotations

import json
import urllib.request
from typing import Any


def fetch_pypi_download_stats(package_name: str = "codegraph-engine", timeout: int = 4) -> dict[str, Any]:
    """Fetch official PyPI download metrics from public pypistats.org API."""
    url = f"https://pypistats.org/api/packages/{package_name}/recent"
    req = urllib.request.Request(url, headers={"User-Agent": "codegraph-cli/3.0.3"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("data", {})
            return {
                "package": package_name,
                "last_day": raw.get("last_day", 0),
                "last_week": raw.get("last_week", 0),
                "last_month": raw.get("last_month", 0),
                "status": "ok",
            }
    except Exception as e:
        return {
            "package": package_name,
            "status": "error",
            "message": str(e),
            "last_day": 0,
            "last_week": 0,
            "last_month": 0,
        }
