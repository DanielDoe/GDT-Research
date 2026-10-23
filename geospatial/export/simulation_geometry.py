#!/usr/bin/env python3
"""Export simulation-ready collision proxies from the building catalog (not render meshes)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "buildings-catalog.json"
OUT_DIR = ROOT / "data" / "simulation"
STUDY = ROOT / "config" / "study_area.json"
DEMO = ROOT / "config" / "demo_district.json"


def footprint_to_geojson_feature(building: dict, representation: str) -> dict:
    ring = building["footprint_wgs84"]
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]
    coords = [[[lon, lat] for lon, lat in ring]]
    height = building["height_m"]
    return {
        "type": "Feature",
        "id": building["id"],
        "geometry": {"type": "Polygon", "coordinates": coords},
        "properties": {
            "gdt_id": building["id"],
            "osm_id": building.get("osm_id"),
            "name": building.get("name"),
            "height_m": height,
            "footprint_area_m2": building.get("footprint_area_m2"),
            "lod": "LOD1",
            "representation": representation,
            "collision": representation == "collision_prism",
            "visual": representation == "visual_proxy",
            "height_source": building.get("height_source"),
            "quality": "catalog_footprint_extrusion",
            "note": "Extruded footprint — not mesh-accurate; replace with LiDAR/refined mesh for LOD2+.",
        },
    }


def in_bbox(building: dict, bbox: dict) -> bool:
    lon, lat = building["longitude"], building["latitude"]
    return (
        bbox["west"] <= lon <= bbox["east"]
        and bbox["south"] <= lat <= bbox["north"]
    )


def export_collection(
    buildings: list[dict],
    bbox: dict | None,
    label: str,
) -> None:
    filtered = [b for b in buildings if not bbox or in_bbox(b, bbox)]
    for rep in ("collision_prism", "visual_proxy"):
        features = [footprint_to_geojson_feature(b, rep) for b in filtered]
        fc = {
            "type": "FeatureCollection",
            "name": f"gdt_{label}_{rep}",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features,
        }
        out = OUT_DIR / f"{label}_{rep}.geojson"
        out.write_text(json.dumps(fc, indent=2), encoding="utf-8")
        print(f"Wrote {out} ({len(features)} features)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    buildings = catalog["buildings"]
    study = json.loads(STUDY.read_text(encoding="utf-8"))
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    export_collection(buildings, study["bbox_wgs84"], "study_area")
    export_collection(buildings, demo["bbox_wgs84"], "demo_district")


if __name__ == "__main__":
    main()
