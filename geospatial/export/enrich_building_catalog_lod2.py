#!/usr/bin/env python3
"""Enrich OSM building catalog with LOD2 metadata and USGS EPQS ground elevations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "geospatial"))

from acquisition.epqs_elevation import query_epqs_batch  # noqa: E402

CATALOG_PUBLIC = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "buildings-catalog.json"
CATALOG_ASSETS = ROOT / "assets" / "buildings" / "buildings-catalog.json"
DEMO = json.loads((ROOT / "config" / "demo_district.json").read_text(encoding="utf-8"))


def in_bbox(lon: float, lat: float, bbox: dict) -> bool:
    return bbox["west"] <= lon <= bbox["east"] and bbox["south"] <= lat <= bbox["north"]


def infer_materials(building_tag: str) -> tuple[str, str, str]:
    tag = (building_tag or "yes").lower()
    if tag in {"church", "cathedral", "chapel"}:
        return "stone", "metal_standing_seam", "LOD2_procedural"
    if tag in {"commercial", "retail", "office", "industrial", "warehouse"}:
        return "concrete", "flat_membrane", "LOD2_procedural"
    if tag in {"apartments", "residential", "house", "detached", "terrace"}:
        return "stucco", "asphalt_shingle", "LOD2_procedural"
    if tag in {"school", "university", "public"}:
        return "brick", "flat_membrane", "LOD2_procedural"
    return "stucco", "asphalt_shingle", "LOD1_procedural"


def enrich_building(b: dict, ground_m: float | None, demo: bool) -> dict:
    facade, roof, method = infer_materials(b.get("building", "yes"))
    has_measured_height = not str(b.get("height_source", "")).startswith("estimated")
    lod = "LOD2" if (demo and ground_m is not None) or has_measured_height else "LOD1"
    if demo and ground_m is not None:
        lod = "LOD2"
    return {
        **b,
        "lod": lod,
        "in_demo_district": demo,
        "ground_elevation_m": round(ground_m, 3) if ground_m is not None else None,
        "ground_elevation_source": "usgs_epqs" if ground_m is not None else None,
        "ground_elevation_datum": "NAVD88_approx_epqs" if ground_m is not None else None,
        "reconstruction_method": "LOD2_procedural" if lod == "LOD2" else "osm2world_monolith",
        "quality_class": "measured_height" if has_measured_height else ("demo_refined" if demo else "estimated"),
        "facade_material": facade,
        "roof_material": roof,
        "collision_ready": True,
        "simulation_proxy": "footprint_extrusion",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-only", action="store_true", help="Only query EPQS for demo district buildings")
    parser.add_argument("--skip-elevation", action="store_true", help="Skip network EPQS calls")
    parser.add_argument("--delay", type=float, default=0.015, help="Delay between EPQS requests (seconds)")
    parser.add_argument("--limit", type=int, default=0, help="Max EPQS queries (0 = all targets)")
    args = parser.parse_args()

    path = CATALOG_PUBLIC if CATALOG_PUBLIC.exists() else CATALOG_ASSETS
    if not path.exists():
        raise FileNotFoundError("Run osm_building_catalog.py first.")

    catalog = json.loads(path.read_text(encoding="utf-8"))
    buildings: list[dict] = catalog["buildings"]
    demo_bbox = DEMO["bbox_wgs84"]

    targets = [
        b
        for b in buildings
        if not args.demo_only or in_bbox(b["longitude"], b["latitude"], demo_bbox)
    ]

    elevations: list[float | None] = [None] * len(targets)
    if not args.skip_elevation and targets:
        if args.limit > 0:
            targets = targets[: args.limit]
        print(f"Querying USGS EPQS for {len(targets)} building centroids...")
        points = [(b["longitude"], b["latitude"]) for b in targets]
        elevations = query_epqs_batch(points, delay_s=args.delay)

    elev_by_id = {targets[i]["id"]: elevations[i] for i in range(len(targets))}

    enriched: list[dict] = []
    lod2_count = 0
    for b in buildings:
        demo = in_bbox(b["longitude"], b["latitude"], demo_bbox)
        ground = elev_by_id.get(b["id"])
        row = enrich_building(b, ground, demo)
        if row["lod"] == "LOD2":
            lod2_count += 1
        enriched.append(row)

    catalog["buildings"] = enriched
    catalog["schema_version"] = 2
    catalog["elevation_notes"] = (
        "ground_elevation_m from USGS EPQS (National Map 3DEP-derived service). "
        "Not a substitute for surveyed building heights."
    )
    catalog["lod2_count"] = lod2_count
    catalog["demo_district"] = DEMO["name"]

    text = json.dumps(catalog, indent=2)
    CATALOG_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PUBLIC.write_bytes(text.encode("utf-8"))
    CATALOG_ASSETS.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_ASSETS.write_bytes(text.encode("utf-8"))
    print(f"Enriched {len(enriched)} buildings ({lod2_count} marked LOD2) -> {CATALOG_PUBLIC}")


if __name__ == "__main__":
    main()
