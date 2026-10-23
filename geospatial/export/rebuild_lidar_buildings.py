#!/usr/bin/env python3
"""Replace downtown blocks with City of Galveston footprints and 2018 LiDAR heights.

Footprints: City GIS building layer (aligned to municipal mapping).
Heights: USGS 3DEP LPC 2018 Coastal Texas, class-6 roof minus class-2 ground.
Visual base in Cesium stays on the globe (height 0). NAVD88 ground is stored
as metadata and is not used as an ellipsoid height.
"""

from __future__ import annotations

import json
import math
import zlib
from pathlib import Path

import laspy
import numpy as np
import requests
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import Polygon, shape

ROOT = Path(__file__).resolve().parents[2]
STUDY = json.loads((ROOT / "config" / "study_area.json").read_text(encoding="utf-8"))
DEMO = json.loads((ROOT / "config" / "demo_district.json").read_text(encoding="utf-8"))
OSM_CATALOG = ROOT / "apps" / "web" / "public" / "assets" / "galveston" / "buildings-catalog.json"
OSM_INDEX = ROOT / "data" / "processed" / "osm" / "osm-building-index.json"
OUT_PUBLIC = OSM_CATALOG
OUT_ASSETS = ROOT / "assets" / "buildings" / "buildings-catalog.json"
LAZ_DIR = ROOT / "data" / "raw" / "lidar"
GIS_QUERY = (
    "https://gis.galvestontx.gov/server/rest/services/Basemap/"
    "Streets_3D_Basemap/MapServer/0/query"
)

BBOX = STUDY.get("reconstruction_bbox_wgs84", STUDY["bbox_wgs84"])
MIN_AREA_M2 = 12.0
MIN_HEIGHT_M = 3.0
MAX_HEIGHT_M = 42.0


def in_bbox(lon: float, lat: float, bbox: dict) -> bool:
    return bbox["west"] <= lon <= bbox["east"] and bbox["south"] <= lat <= bbox["north"]


def ring_area_m2(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0
    avg_lat = sum(c[1] for c in coords) / len(coords)
    m_lon = 111_320.0 * math.cos(math.radians(avg_lat))
    m_lat = 111_320.0
    area = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i][0] * m_lon, coords[i][1] * m_lat
        x2, y2 = coords[i + 1][0] * m_lon, coords[i + 1][1] * m_lat
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def centroid(coords: list[tuple[float, float]]) -> tuple[float, float]:
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


def estimate_height(area: float, tag: str) -> float:
    tag = (tag or "yes").lower()
    if tag in {"warehouse", "industrial", "hangar"}:
        return 8.5
    if tag in {"commercial", "retail", "office", "public", "school", "university"}:
        if area > 2500:
            return 16.0
        if area > 800:
            return 12.0
        return 8.5
    if tag in {"church", "cathedral", "chapel"}:
        return 14.0
    if area < 90:
        return 4.2
    if area < 220:
        return 6.2
    if area < 500:
        return 7.5
    if area < 1200:
        return 10.5
    return 13.0


def infer_materials(tag: str, area: float, salt: int) -> tuple[str, str, float]:
    tag = (tag or "yes").lower()
    if tag in {"church", "cathedral", "chapel"}:
        return "stone", "metal", 2.2
    if tag in {"warehouse", "industrial", "hangar"}:
        return "metal_panel", "metal", 0.6
    if tag in {"commercial", "retail", "office", "public"} or area > 900:
        roof = "flat_membrane" if area > 400 else "asphalt_shingle"
        facade = "brick" if salt % 2 == 0 else "masonry"
        rise = 0.55 if roof == "flat_membrane" else 1.4
        return facade, roof, rise
    if tag in {"apartments", "residential"}:
        return "clapboard", "asphalt_shingle", 1.8
    if tag in {"house", "detached", "terrace", "semidetached_house"}:
        facade = "clapboard" if salt % 3 else "wood"
        return facade, "asphalt_shingle", 2.1
    if area < 280:
        facade = ("clapboard", "wood", "stucco")[salt % 3]
        return facade, "asphalt_shingle", 1.9
    return "brick", "asphalt_shingle", 1.5


def fetch_city_footprints() -> list[dict]:
    features: list[dict] = []
    offset = 0
    while True:
        response = requests.get(
            GIS_QUERY,
            params={
                "geometry": f"{BBOX['west']},{BBOX['south']},{BBOX['east']},{BBOX['north']}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "XREF,DISTRICT,STATUS,OBJECTID",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": 2000,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("features") or []
        features.extend(batch)
        if not payload.get("exceededTransferLimit") and len(batch) < 2000:
            break
        if not batch:
            break
        offset += len(batch)
    return features


def load_osm_index() -> list[dict]:
    if OSM_CATALOG.exists():
        catalog = json.loads(OSM_CATALOG.read_text(encoding="utf-8"))
        rows = catalog.get("buildings") or []
        if rows and str(rows[0].get("source", "")).startswith("OpenStreetMap"):
            slim = [
                {
                    "osm_id": row.get("osm_id") or "",
                    "name": row.get("name"),
                    "building": row.get("building") or "yes",
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                }
                for row in rows
                if row.get("latitude") is not None
            ]
            OSM_INDEX.parent.mkdir(parents=True, exist_ok=True)
            OSM_INDEX.write_text(json.dumps(slim), encoding="utf-8")
            return slim
    if OSM_INDEX.exists():
        return json.loads(OSM_INDEX.read_text(encoding="utf-8"))
    return []


def nearest_osm(rows: list[dict], lon: float, lat: float, max_m: float = 22.0) -> dict | None:
    m_lon = 111_320.0 * math.cos(math.radians(lat))
    best = None
    best_d = max_m
    for row in rows:
        dx = (row["longitude"] - lon) * m_lon
        dy = (row["latitude"] - lat) * 111_320.0
        dist = math.hypot(dx, dy)
        if dist < best_d:
            best_d = dist
            best = row
    return best


def exterior_ring(geom) -> list[tuple[float, float]] | None:
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    if geom.geom_type != "Polygon":
        return None
    coords = [(float(x), float(y)) for x, y in geom.exterior.coords]
    if len(coords) < 4:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def load_lidar() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Transformer]:
    paths = sorted(LAZ_DIR.glob("stratmap18-*.laz"))
    if len(paths) < 2:
        raise FileNotFoundError(
            f"Expected stratmap18 LiDAR tiles in {LAZ_DIR}. Found {len(paths)}."
        )

    west, south, east, north = BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]
    arrays: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
    to_native: Transformer | None = None

    for path in paths:
        print(f"reading {path.name}", flush=True)
        las = laspy.read(path)
        crs = las.header.parse_crs()
        if crs is None:
            raise RuntimeError(f"{path.name} has no CRS")
        to_native = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        cx, cy = to_native.transform(
            [west, east, west, east],
            [south, south, north, north],
        )
        pad = 40.0
        minx, maxx = min(cx) - pad, max(cx) + pad
        miny, maxy = min(cy) - pad, max(cy) + pad
        x = np.asarray(las.x, dtype=np.float64)
        y = np.asarray(las.y, dtype=np.float64)
        z = np.asarray(las.z, dtype=np.float64)
        cls = np.asarray(las.classification, dtype=np.uint8) & 31
        keep = (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
        print(f"  kept {int(keep.sum()):,} / {len(x):,} points inside study bbox", flush=True)
        arrays.append((x[keep], y[keep], z[keep], cls[keep]))
        del las

    x = np.concatenate([a[0] for a in arrays])
    y = np.concatenate([a[1] for a in arrays])
    z = np.concatenate([a[2] for a in arrays])
    cls = np.concatenate([a[3] for a in arrays])
    sample = z[(cls == 2) | (cls == 6)]
    if sample.size and float(np.median(np.abs(sample))) > 80:
        z = z * 0.3048006096012192
    assert to_native is not None
    return x, y, z, cls, to_native


def build_point_grid(
    x: np.ndarray,
    y: np.ndarray,
    cell_m: float = 40.0,
) -> tuple[float, float, float, dict[tuple[int, int], np.ndarray]]:
    ix = np.floor(x / cell_m).astype(np.int32)
    iy = np.floor(y / cell_m).astype(np.int32)
    order = np.argsort(ix.astype(np.int64) * 1_000_000 + iy, kind="mergesort")
    ix = ix[order]
    iy = iy[order]
    keys = ix.astype(np.int64) * 1_000_000 + iy
    breaks = np.flatnonzero(np.diff(keys)) + 1
    starts = np.r_[0, breaks]
    ends = np.r_[breaks, len(order)]
    grid: dict[tuple[int, int], np.ndarray] = {}
    for start, end in zip(starts, ends):
        grid[(int(ix[start]), int(iy[start]))] = order[start:end]
    return cell_m, float(x.min()), float(y.min()), grid


def measure_height(
    ring_lonlat: list[tuple[float, float]],
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    cls: np.ndarray,
    to_native: Transformer,
    grid: dict[tuple[int, int], np.ndarray],
    cell_m: float,
) -> tuple[float | None, float | None]:
    native = [to_native.transform(lon, lat) for lon, lat in ring_lonlat]
    poly = Polygon(native)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None, None
    minx, miny, maxx, maxy = poly.bounds
    i0, i1 = int(np.floor(minx / cell_m)), int(np.floor(maxx / cell_m))
    j0, j1 = int(np.floor(miny / cell_m)), int(np.floor(maxy / cell_m))
    chunks = [grid[(i, j)] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) if (i, j) in grid]
    if not chunks:
        return None, None
    idx = chunks[0] if len(chunks) == 1 else np.concatenate(chunks)
    if idx.size < 6:
        return None, None
    px = x[idx]
    py = y[idx]
    pz = z[idx]
    pc = cls[idx]
    inside = contains_xy(poly, px, py)
    if int(inside.sum()) < 6:
        return None, None
    pz = pz[inside]
    pc = pc[inside]
    ground_pts = pz[pc == 2]
    if ground_pts.size >= 4:
        ground = float(np.median(ground_pts))
    else:
        ground = float(np.percentile(pz, 15))
    building_pts = pz[pc == 6]
    if building_pts.size >= 10:
        roof = float(np.percentile(building_pts, 90))
    else:
        above = pz[(pz > ground + 2.0) & ~np.isin(pc, [2, 7, 9, 10, 18])]
        if above.size < 10:
            return None, round(ground, 3)
        roof = float(np.percentile(above, 85))
    height = roof - ground
    if not math.isfinite(height):
        return None, round(ground, 3)
    return height, round(ground, 3)


def main() -> None:
    print("fetching City of Galveston footprints")
    features = fetch_city_footprints()
    print(f"  features: {len(features)}")
    osm_rows = load_osm_index()

    print("loading LiDAR")
    x, y, z, cls, to_native = load_lidar()
    print(f"  study points: {len(z):,}", flush=True)
    cell_m, _origin_x, _origin_y, grid = build_point_grid(x, y)
    print(f"  point grid cells: {len(grid):,}", flush=True)

    buildings: list[dict] = []
    lidar_count = 0
    for feature in features:
        props = feature.get("properties") or {}
        geom = shape(feature["geometry"])
        ring = exterior_ring(geom)
        if ring is None:
            continue
        area = ring_area_m2(ring)
        if area < MIN_AREA_M2:
            continue
        clon, clat = centroid(ring[:-1])
        if not in_bbox(clon, clat, BBOX):
            continue
        xref = str(props.get("XREF") or props.get("OBJECTID") or len(buildings))
        osm = nearest_osm(osm_rows, clon, clat) if osm_rows else None
        tag = (osm or {}).get("building") or "yes"
        name = (osm or {}).get("name") or f"Building {xref}"
        if name.startswith("Building ") and osm and osm.get("name"):
            name = osm["name"]
        salt = zlib.adler32(xref.encode("utf-8")) % 997
        facade, roof, rise = infer_materials(tag, area, salt)
        measured, ground = measure_height(ring, x, y, z, cls, to_native, grid, cell_m)
        if len(buildings) % 500 == 0:
            print(f"  measured {len(buildings)} footprints", flush=True)
        if measured is not None and MIN_HEIGHT_M <= measured <= MAX_HEIGHT_M:
            height = measured
            height_source = "usgs_3dep_lpc_2018_p90"
            quality = "lidar_height"
            lidar_count += 1
        else:
            height = estimate_height(area, tag)
            height_source = "estimated:footprint_class"
            quality = "estimated"
        if height < rise + 2.2:
            rise = max(0.4, height * 0.22)
        buildings.append(
            {
                "id": f"gdt-gis-{xref}",
                "osm_id": (osm or {}).get("osm_id") or "",
                "gis_xref": xref,
                "name": name,
                "building": tag,
                "latitude": clat,
                "longitude": clon,
                "height_m": round(float(height), 2),
                "height_source": height_source,
                "footprint_area_m2": round(area, 1),
                "footprint_wgs84": [[c[0], c[1]] for c in ring],
                "source": "City of Galveston GIS footprints; USGS 3DEP LPC 2018 heights",
                "lod": "LOD2",
                "in_demo_district": in_bbox(clon, clat, DEMO["bbox_wgs84"]),
                "ground_elevation_m": ground,
                "ground_elevation_source": "usgs_3dep_lpc_2018_class2" if ground is not None else None,
                "ground_elevation_datum": "NAVD88_GEOID12B_meters" if ground is not None else None,
                "reconstruction_method": "city_footprint_lidar_extrusion",
                "quality_class": quality,
                "facade_material": facade,
                "roof_material": roof,
                "roof_rise_m": round(rise, 2),
                "collision_ready": True,
                "simulation_proxy": "footprint_extrusion",
            }
        )

    payload = {
        "study_area": STUDY["name"],
        "count": len(buildings),
        "default_height_m": 7.5,
        "schema_version": 3,
        "lod2_count": lidar_count,
        "demo_district": DEMO["name"],
        "elevation_notes": (
            "Building outlines are City of Galveston GIS footprints for the study bbox. "
            "height_m is roof-minus-ground from USGS 3DEP 2018 LPC where class-6 or "
            "above-ground returns exist (NAVD88 meters). Cesium extrudes from globe height 0 "
            "so volumes sit on imagery; ground_elevation_m is orthometric metadata, not an ellipsoid offset. "
            "Materials are procedural. This is LOD2 massing, not photogrammetry."
        ),
        "buildings": buildings,
    }
    text = json.dumps(payload)
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    OUT_ASSETS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.write_text(text, encoding="utf-8")
    OUT_ASSETS.write_text(text, encoding="utf-8")
    heights = [b["height_m"] for b in buildings]
    print(
        f"wrote {len(buildings)} buildings "
        f"({lidar_count} lidar heights, {len(buildings) - lidar_count} estimated) "
        f"height {min(heights):.1f}-{max(heights):.1f} m"
    )


if __name__ == "__main__":
    main()
