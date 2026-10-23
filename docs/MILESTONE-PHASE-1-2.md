# Milestone report — Phase 1 viewer + Phase 2 OSM2World (initial)

Date: 2026-10-23

## Implemented features

### Phase 1 — Functional CesiumJS viewer

- Next.js 15 + TypeScript research dashboard under `apps/web`
- CesiumJS globe centered on Galveston with study-area polygon overlay
- Camera presets (overview, downtown, harbor, island, demonstration area)
- Layer manager, object inspector shell, status bar, building-source switch
- OpenStreetMap raster imagery when no Cesium ion token is configured
- Cesium World Terrain + Cesium OSM Buildings when `NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN` is set
- Production build verified (`npm run build`)

### Phase 2 — OSM2World reconstruction (demonstration tile)

- Reproducible Overpass download for `config/study_area.json` bbox
- OSM2World 0.4.0 installed from [osm2world.org](https://osm2world.org/download/files/0.4.0/)
- Portable Temurin 17 JRE bundled under `geospatial/osm2world/jre` (project-local, not committed)
- Automated export to **GLB** (~6.1 MB) and publish to `apps/web/public/assets/galveston/galveston-demo.glb`
- Viewer toggle: **Reference OSM Buildings** vs **GDT OSM2World reconstruction** (not shown together by default)

### Supporting infrastructure

- FastAPI stub (`services/api/main.py`) with `/health` and `/api/v1/study-area`
- Dataset manifest updated on OSM download (`data/manifests/dataset_manifest.json`)
- Unit tests for study-area config (`tests/test_study_area_config.py`)

## Generated 3D assets

| Asset | Path | Size |
| --- | --- | --- |
| OSM2World GLB | `assets/buildings/osm2world/galveston-study.glb` | ~6.1 MB |
| Web-served copy | `apps/web/public/assets/galveston/galveston-demo.glb` | ~6.1 MB |
| Transform sidecar | `assets/buildings/galveston-demo.transform.json` | anchor WGS84 |

## Source datasets

| Dataset | Source | File |
| --- | --- | --- |
| OSM extract | OpenStreetMap (ODbL) via Overpass | `data/processed/osm/galveston-study.osm` (~724 KB) |

## Known limitations (document honestly)

1. **Georeferencing:** The GLB is anchored at the configured local origin (`29.3015, -94.79565`). Fine alignment against reference imagery must be validated visually; rotation/offset may need adjustment in `galveston-demo.transform.json`.
2. **Per-building picking:** The exported GLB is a combined mesh; per-building inspector metadata is not yet mapped from OSM IDs. A companion metadata pipeline is planned.
3. **Cesium ion:** Reference OSM Buildings and World Terrain require a free Cesium ion token. Without it, the app uses OSM tiles + ellipsoid terrain (still shows Galveston and the GDT model).
4. **LiDAR / PostGIS:** Not started in this iteration (per stop instruction before large LiDAR work).
5. **Docker:** Docker Desktop was not running; OSM2World uses the bundled portable JRE instead.
6. **Java system install:** Temurin MSI via winget may still be completing separately; the pipeline does not depend on it.

## How to run

```powershell
cd C:\Users\danie\Downloads\GDT-Research\apps\web
copy .env.example .env.local
# Optional: set NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN in .env.local

npm install
npm run dev
```

Open http://localhost:3000

Regenerate the 3D city:

```powershell
cd C:\Users\danie\Downloads\GDT-Research
powershell -ExecutionPolicy Bypass -File scripts\run_osm2world_pipeline.ps1
```

## Recommended next milestone

Phase 3 (LiDAR terrain + building height refinement) **after approval**, plus:

- PostGIS schema + ingest OSM footprints
- 3D Tiles tiling pipeline for the demonstration area
- OSM → per-feature metadata sidecar for inspector/picking
- Formal validation report comparing GDT GLB vs reference layers
