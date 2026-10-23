#!/usr/bin/env python3
"""Convert OSM2World OBJ output to georeferenced GLB for Cesium."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "config" / "study_area.json").read_text(encoding="utf-8"))
ORIGIN = CONFIG["local_origin_wgs84"]

OSM2WORLD_GLB = ROOT / "assets" / "buildings" / "osm2world" / "galveston-study.glb"
OBJ = ROOT / "assets" / "buildings" / "osm2world" / "galveston-study.obj"
GLB_ASSET = ROOT / "assets" / "buildings" / "galveston-demo.glb"
PUBLIC_GLB = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "galveston-demo.glb"
PUBLIC_TRANSFORM = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "galveston-demo.transform.json"
META_OUT = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "buildings-metadata.json"
TRANSFORM_OUT = ROOT / "assets" / "buildings" / "galveston-demo.transform.json"


def main() -> None:
    GLB_ASSET.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_GLB.parent.mkdir(parents=True, exist_ok=True)

    if OSM2WORLD_GLB.exists():
        shutil.copy2(OSM2WORLD_GLB, GLB_ASSET)
        shutil.copy2(OSM2WORLD_GLB, PUBLIC_GLB)
    elif OBJ.exists():
        mesh = trimesh.load(OBJ, force="mesh", process=True)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
        mesh.export(GLB_ASSET)
        shutil.copy2(GLB_ASSET, PUBLIC_GLB)
    else:
        raise FileNotFoundError(
            f"Missing OSM2World output. Expected {OSM2WORLD_GLB} or {OBJ}. Run scripts/run_osm2world_pipeline.ps1"
        )

    transform = {
        "crs": "local_enu",
        "anchor_wgs84": ORIGIN,
        "comment": "Model placed at anchor using Cesium East-North-Up frame; verify rotation during validation.",
        "recommended_heading_deg": 0,
        "scale": 1.0,
    }
    transform_text = json.dumps(transform, indent=2)
    TRANSFORM_OUT.write_text(transform_text, encoding="utf-8")
    PUBLIC_TRANSFORM.write_text(transform_text, encoding="utf-8")

    meta = [
        {
            "id": "gdt-reconstructed-city",
            "source": "OpenStreetMap + OSM2World",
            "latitude": ORIGIN["latitude"],
            "longitude": ORIGIN["longitude"],
            "height_m": None,
            "name": "Downtown Galveston OSM2World tile",
        }
    ]
    META_OUT.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Exported {GLB_ASSET} ({GLB_ASSET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
