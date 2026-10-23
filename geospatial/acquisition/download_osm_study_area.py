#!/usr/bin/env python3
"""Download OpenStreetMap XML for the configured Galveston study area."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "study_area.json"
RAW_DIR = ROOT / "data" / "raw" / "osm"
PROCESSED_DIR = ROOT / "data" / "processed" / "osm"
MANIFEST = ROOT / "data" / "manifests" / "dataset_manifest.json"


def load_bbox() -> tuple[float, float, float, float]:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bb = cfg["bbox_wgs84"]
    return bb["south"], bb["west"], bb["north"], bb["east"]


def overpass_query(south: float, west: float, north: float, east: float) -> str:
    return f"""
[out:xml][timeout:180];
(
  way["building"]({south},{west},{north},{east});
  relation["building"]({south},{west},{north},{east});
  way["highway"]({south},{west},{north},{east});
  way["natural"="water"]({south},{west},{north},{east});
  way["waterway"]({south},{west},{north},{east});
  way["landuse"]({south},{west},{north},{east});
);
(._;>;);
out body;
""".strip()


def download_osm_xml(query: str) -> bytes:
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_err: Exception | None = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("User-Agent", "GDT-Research/1.0 (research; contact: local)")
            with urllib.request.urlopen(req, timeout=240) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2)
    raise RuntimeError(f"Overpass download failed: {last_err}")


def update_manifest(out_path: Path) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if MANIFEST.exists():
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = {
        "dataset_name": "OpenStreetMap study extract",
        "source": "OpenStreetMap contributors",
        "download_url": "https://www.openstreetmap.org/",
        "acquisition_date": time.strftime("%Y-%m-%d"),
        "coverage": str(load_bbox()),
        "crs": "EPSG:4326",
        "vertical_datum": None,
        "resolution": "Vector features",
        "license": "ODbL 1.0 — attribution required",
        "processing_status": "downloaded",
        "output_path": str(out_path.relative_to(ROOT)),
        "known_limitations": "Height tags may be missing; requires OSM2World reconstruction assumptions.",
    }
    entries = [e for e in entries if e.get("dataset_name") != entry["dataset_name"]]
    entries.append(entry)
    MANIFEST.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def main() -> int:
    south, west, north, east = load_bbox()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    query = overpass_query(south, west, north, east)
    xml = download_osm_xml(query)
    if b"<osm" not in xml[:4096]:
        print("Unexpected Overpass response", file=sys.stderr)
        return 1

    raw_path = RAW_DIR / "galveston-study-overpass.osm"
    out_path = PROCESSED_DIR / "galveston-study.osm"
    raw_path.write_bytes(xml)
    out_path.write_bytes(xml)
    update_manifest(out_path)
    print(f"Wrote {out_path} ({len(xml)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
