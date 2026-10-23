#!/usr/bin/env python3
"""Build a Cesium HeightmapTerrainProvider JSON grid for the demo district (USGS EPQS)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "geospatial"))

from acquisition.epqs_elevation import query_epqs_batch  # noqa: E402

DEMO = json.loads((ROOT / "config" / "demo_district.json").read_text(encoding="utf-8"))
OUT = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "demo-district-heightmap.json"
OUT_ASSETS = ROOT / "assets" / "terrain" / "demo-district-heightmap.json"

WIDTH = 16
HEIGHT = 16


def main() -> None:
    bbox = DEMO["bbox_wgs84"]
    west, east = bbox["west"], bbox["east"]
    south, north = bbox["south"], bbox["north"]

    points: list[tuple[float, float]] = []
    for row in range(HEIGHT):
        v = row / (HEIGHT - 1)
        lat = south + (north - south) * v
        for col in range(WIDTH):
            u = col / (WIDTH - 1)
            lon = west + (east - west) * u
            points.append((lon, lat))

    print(f"Sampling {len(points)} EPQS points for demo district heightmap…")
    samples = query_epqs_batch(points, delay_s=0.03)
    fallback = next((s for s in samples if s is not None), 2.0)
    heights = [float(s if s is not None else fallback) for s in samples]

    payload = {
        "name": DEMO["name"],
        "source": "USGS EPQS (3DEP-derived)",
        "datum_note": "EPQS returns approximate NAVD88-equivalent meters; validate for flood experiments.",
        "rectangle_wgs84": bbox,
        "width": WIDTH,
        "height": HEIGHT,
        "heights_m": heights,
        "min_m": min(heights),
        "max_m": max(heights),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUT_ASSETS.parent.mkdir(parents=True, exist_ok=True)
    OUT_ASSETS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} (range {payload['min_m']:.2f}–{payload['max_m']:.2f} m)")


if __name__ == "__main__":
    main()
