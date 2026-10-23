"""USGS Elevation Point Query Service (EPQS) — ground elevation at WGS84 points."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

EPQS_URL = "https://epqs.nationalmap.gov/v1/json"


def query_epqs_meters(longitude: float, latitude: float, timeout_s: float = 20.0) -> float | None:
    params = urllib.parse.urlencode(
        {
            "x": f"{longitude:.8f}",
            "y": f"{latitude:.8f}",
            "units": "Meters",
            "wkid": "4326",
        }
    )
    url = f"{EPQS_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("value")
        if raw is None:
            return None
        return float(raw)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def query_epqs_batch(
    points: list[tuple[float, float]],
    delay_s: float = 0.05,
) -> list[float | None]:
    out: list[float | None] = []
    for i, (lon, lat) in enumerate(points):
        out.append(query_epqs_meters(lon, lat))
        if delay_s > 0 and i + 1 < len(points):
            time.sleep(delay_s)
    return out
