# Immersive 3D environment roadmap

This document aligns the Galveston Digital Twin with phased delivery of **real geometry**, **simulation-ready exports**, and **immersive navigation** without replacing the existing Next.js + CesiumJS research dashboard.

**Data sourcing and photorealistic feasibility:** see **`docs/GALVESTON-HIGH-FIDELITY-DATA-ASSESSMENT.md`** (Stage 1–2 gate before full-city work).

## Current state (Phase A — complete)

See **`docs/GEOMETRY-AUDIT.md`** and **`docs/geometry-audit-report.json`** (regenerate via `python geospatial/validation/audit_geometry.py`).

- **LOD 1** OSM2World GLB deployed: 1,999 internal meshes, 566 catalog footprints, monolithic export.
- **Terrain**: ellipsoid by default; Cesium World Terrain when Ion token is set. Local USGS/TNRIS DEM **not yet** ingested.
- **Satellite**: aerial imagery is **2D**; photographed structures are not mesh geometry.
- **Selection**: footprint catalog + extruded highlight, not per-mesh GLB picking.
- **Walk mode**: terrain clamp + WASD; **no building collision**.

## Phase B — Terrain and imagery alignment

| Task | Owner / path |
|------|----------------|
| Acquire USGS 3DEP / TNRIS LiDAR for demo district | `geospatial/acquisition/` |
| Build NAVD88-aware DEM | `geospatial/terrain/` (planned) |
| Publish Cesium terrain or custom mesh | Ion upload or quantized-mesh pipeline |
| Document vertical datum offsets vs ellipsoid | validation report |
| True orthophoto / terrain texture study | legal review only |

## Phase C — LOD 2 building reconstruction (partial — in repo)

| Task | Status |
|------|--------|
| USGS EPQS ground elevation on catalog | `geospatial/export/enrich_building_catalog_lod2.py` |
| Independent per-building volumes in Cesium | `apps/web/lib/cesium/catalog-building-layer.ts` |
| Procedural facade/roof materials by OSM type | `apps/web/lib/cesium/procedural-materials.ts` |
| Demo district bbox | `config/demo_district.json` |
| LiDAR building height refinement | **Not yet** — still mostly default 10 m |
| Per-building OSM2World / Blender meshes | **Not yet** — monolithic GLB remains LOD1 |

**LOD 2 is not photorealistic** unless source measurements support it.

## Phase D — Immersive navigation (partial — in viewer)

- **Orbit / fly / walk** — `NavigationControls` + `FirstPersonWalkController`
- **Scene visualization modes** — satellite-only vs satellite+3D vs research geometry
- **Scenario save/restore** — `localStorage` via `lib/scene-persistence.ts`

Remaining: building collision, navigation graphs, physics engine.

## Phase E — Simulation geometry (partial)

Run:

```bash
python geospatial/export/simulation_geometry.py
```

Outputs under `data/simulation/`:

- `study_area_collision_prism.geojson`
- `demo_district_collision_prism.geojson`

These are **extruded footprint prisms** for LOD1 — not mesh-accurate colliders.

## Phase F — High-fidelity demonstration district

Target: `config/demo_district.json` (~2 blocks). Requires LOD2+ data acquisition and licensed sources. **High fidelity** visualization mode in the UI is a **placeholder** until LOD3 assets exist.

## Phase G — Physics-capable prototype

See **`docs/UNREAL-INTEGRATION.md`**. Benchmark Unreal + Cesium for Unreal with the same GLB, DEM, and collision GeoJSON. Do **not** migrate the web app until the prototype proves value.

## LOD definitions

| LOD | Description | Status |
|-----|-------------|--------|
| LOD1 | OSM footprints + OSM2World procedural | **Live** |
| LOD2 | LiDAR heights, refined roofs, materials | Planned |
| LOD3 | Licensed photogrammetry / textured meshes | Not available in repo |

## Validation metrics (targets)

| Metric | Current | Target (demo district) |
|--------|---------|-------------------------|
| Footprint RMSE | Not measured | ≤ 2 m vs reference GIS |
| Height error | ~default 10 m for 565/566 bldgs | ≤ 1 m where LiDAR exists |
| Missing buildings | Unknown | < 5% vs OSM |
| Walk mode FPS | Shown in status bar | ≥ 30 fps on mid GPU |
| Collision vs visual | N/A (prisms only) | Documented offset |

## Licensing

- No Google/Apple 3D tiles.
- ArcGIS, Cesium Ion, OSM, USGS/TNRIS — follow each provider’s terms.
- Document tokens in `apps/web/.env.example` only.
