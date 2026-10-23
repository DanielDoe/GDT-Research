# Unreal Engine / physics simulation integration plan

Goal: one **authoritative geographic dataset** in `GDT-Research`, reused in **CesiumJS** (web) and **Unreal** (simulation), without assuming identical material or collision semantics.

## Authoritative data (keep in repo / `data/`)

| Asset | Format | Role |
|--------|--------|------|
| Study area | `config/study_area.json` | Bbox, ENU origin, camera presets |
| OSM extract | `data/processed/osm/*.osm` | Footprints, tags, roads |
| Building catalog | `assets/buildings/buildings-catalog.json` | IDs, heights, footprints WGS84 |
| Reconstructed city | `assets/buildings/galveston-demo.glb` | Visual mesh (OSM2World) |
| Transform sidecar | `galveston-demo.transform.json` | ENU anchor + heading |
| Future terrain | GeoTIFF / quantized mesh | LiDAR-derived surface |
| Scene objects | JSON registry (web store → export) | Dynamic entities (UAV, sensors) |

## Coordinate systems

- **Storage / APIs:** WGS84 (`EPSG:4326`).
- **Local engineering / OSM2World export:** ENU meters about `local_origin_wgs84`.
- **Unreal:** typically **left-handed Z-up**; convert from ENU (East-North-Up) with a fixed rotation documented in export scripts (do not hard-code in multiple places — single `geospatial/export/coordinate_frames.py` recommended).

## Export path to Unreal

1. **Buildings** — GLB/OBJ from OSM2World → Blender cleanup → FBX with **one mesh per building** where possible; collision as simplified convex hulls or UCX meshes.
2. **Terrain** — PDAL pipeline on TNRIS LiDAR → DEM GeoTIFF → Unreal Landscape or **Cesium for Unreal** tileset.
3. **Identifiers** — preserve `gdt-building-{osm_id}` on mesh/user data for traceability.
4. **Materials** — re-author in Unreal; do not expect glTF materials to transfer literally.

## Integration options

| Option | Pros | Cons |
|--------|------|------|
| **Cesium for Unreal** + same Ion/3D Tiles | Geographic parity with web | Licensing, tile hosting, collision separate |
| **Import static meshes + custom georeferencing** | Full physics/collision control | Manual alignment maintenance |
| **Hybrid** — Cesium globe + imported local meshes | Good for downtown high-detail | Two systems to sync |

## Collision & simulation

- **Static:** building collision meshes generated from footprints + heights (catalog) or LiDAR.
- **Dynamic:** scene objects (UAV/UGV) as Unreal actors; state from future API / ROS bridge — **not** implemented in web viewer.
- **Sensors:** attach to actors; web demo objects are placeholders only.

## Recommended next implementation steps

1. Add `geospatial/export/unreal_city_pack.py` — FBX/GLB split by building ID + `coordinates.json`.
2. PostGIS store for footprints (Phase 3 charter).
3. CI validation: bbox overlap OSM ↔ mesh bounds in ENU.
4. Pilot **Cesium for Unreal** level using same study bbox and Ion token policy as web.

## Licensing note

Do not redistribute proprietary imagery or LiDAR outside provider terms. Document tokens (Ion, Esri, TNRIS) in `.env.example` only.
