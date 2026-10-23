#!/usr/bin/env python3
"""Export OSM building footprints + heights for Cesium picking and inspection."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OSM_PATH = ROOT / "data" / "processed" / "osm" / "galveston-study.osm"
CONFIG = json.loads((ROOT / "config" / "study_area.json").read_text(encoding="utf-8"))
DEFAULT_HEIGHT = float(CONFIG.get("default_building_height_m", 10))
OUT_PUBLIC = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "buildings-catalog.json"
OUT_ASSETS = ROOT / "assets" / "buildings" / "buildings-catalog.json"


def parse_height(tags: dict[str, str]) -> tuple[float, str]:
    if "height" in tags:
        raw = tags["height"].replace("m", "").strip()
        try:
            return float(raw), "osm:height"
        except ValueError:
            pass
    if "building:levels" in tags:
        try:
            levels = float(tags["building:levels"])
            return levels * 3.2, "osm:building:levels"
        except ValueError:
            pass
    if "levels" in tags:
        try:
            levels = float(tags["levels"])
            return levels * 3.2, "osm:levels"
        except ValueError:
            pass
    return DEFAULT_HEIGHT, "estimated:default"


def ring_area_m2(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0
    avg_lat = sum(c[1] for c in coords) / len(coords)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(avg_lat))
    area = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        x1, y1 = lon1 * m_per_deg_lon, lat1 * m_per_deg_lat
        x2, y2 = lon2 * m_per_deg_lon, lat2 * m_per_deg_lat
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def centroid(coords: list[tuple[float, float]]) -> tuple[float, float]:
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


def main() -> None:
    if not OSM_PATH.exists():
        raise FileNotFoundError(f"Missing {OSM_PATH}. Run OSM acquisition first.")

    root = ET.parse(OSM_PATH).getroot()
    nodes: dict[str, tuple[float, float]] = {}
    for node in root.findall("node"):
        nid = node.get("id")
        if nid is None:
            continue
        nodes[nid] = (float(node.get("lon")), float(node.get("lat")))

    buildings: list[dict] = []
    for way in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in way.findall("tag") if t.get("k")}
        if tags.get("building") is None:
            continue
        refs = [nd.get("ref") for nd in way.findall("nd") if nd.get("ref")]
        coords: list[tuple[float, float]] = []
        for ref in refs:
            if ref in nodes:
                coords.append(nodes[ref])
        if len(coords) < 3:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        height_m, height_source = parse_height(tags)
        clon, clat = centroid(coords)
        osm_id = way.get("id", "")
        bid = f"gdt-building-{osm_id}"
        name = tags.get("name") or tags.get("addr:housenumber") or f"Building {osm_id}"
        buildings.append(
            {
                "id": bid,
                "osm_id": osm_id,
                "name": name,
                "building": tags.get("building", "yes"),
                "latitude": clat,
                "longitude": clon,
                "height_m": round(height_m, 2),
                "height_source": height_source,
                "footprint_area_m2": round(ring_area_m2(coords), 1),
                "footprint_wgs84": [[lon, lat] for lon, lat in coords],
                "source": "OpenStreetMap",
            }
        )

    payload = {
        "study_area": CONFIG["name"],
        "count": len(buildings),
        "default_height_m": DEFAULT_HEIGHT,
        "buildings": buildings,
    }
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    OUT_ASSETS.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_PUBLIC.write_text(text, encoding="utf-8")
    OUT_ASSETS.write_text(text, encoding="utf-8")
    print(f"Wrote {len(buildings)} buildings to {OUT_PUBLIC}")


if __name__ == "__main__":
    main()
