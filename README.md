# Galveston Digital Twin Research Testbed (GDT-Research)

Research-grade, modular 3D digital twin platform for **Galveston, Texas**.

## Architecture (three layers)

1. **Geographic data layer** — OSM, municipal GIS, LiDAR (acquisition under `geospatial/`, storage under `data/`)
2. **3D reconstruction layer** — OSM2World + Blender/Python refinement (`geospatial/osm2world/`, `assets/`)
3. **Visualization layer** — Next.js + CesiumJS (`apps/web/`)

Preferred pipeline:

**Galveston GIS + OSM + LiDAR → preprocessing → OSM2World → refinement → GLB / 3D Tiles → CesiumJS**

## Repository layout

```text
apps/web/              Interactive research dashboard (CesiumJS)
services/api/          FastAPI geospatial services (stub)
geospatial/            Acquisition, OSM2World, validation scripts
config/study_area.json Demonstration bbox + camera presets
data/                  Raw/processed data + manifests (large files gitignored)
assets/                Generated GLB/tilesets (gitignored)
database/migrations/   PostGIS (planned)
simulations/           Future modules (not implemented)
docs/                  Architecture + milestone reports
scripts/               One-command pipelines
```

## Quick start (viewer)

```powershell
cd apps/web
copy .env.example .env.local
npm install
npm run dev
```

Optional: add `NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN` in `.env.local` for Cesium World Terrain and **Cesium OSM Buildings** reference layer.

Default basemap is **Esri World Imagery** (aerial); OpenStreetMap street tiles are optional in the viewer imagery dropdown. See [rendering diagnosis](docs/RENDERING-DIAGNOSIS.md).

## Regenerate downtown OSM2World model

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_osm2world_pipeline.ps1
```

This downloads OSM for the study area, runs OSM2World 0.4.0, and copies `galveston-demo.glb` into the web app.

## Full reconstruction (LOD2 catalog + demo terrain + simulation exports)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_full_reconstruction_pipeline.ps1
```

Adds USGS EPQS ground elevations, procedural LOD2 materials metadata, demo-district heightmap terrain, collision GeoJSON, and refreshes `docs/GEOMETRY-AUDIT.md`.

In the viewer, choose **GDT: Independent catalog volumes (LOD2)** or scene mode **High fidelity (demo district)** for per-building meshes with hide/select support.

## Study area

Configured in `config/study_area.json` (~1.5 km² downtown Galveston). Sync a copy exists at `apps/web/lib/data/study_area.json` for the frontend.

## Research agents

The viewer is unchanged. **Map** configures the basemap, terrain, and reconstruction. **Agents** selects research families and, for Weather, requests real station observations.

```powershell
.\.venv\Scripts\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000
```

Rainfall and wind read NOAA ASOS reports (Iowa Environmental Mesonet historical hourly files, and the National Weather Service API for recent observations). Other agent families are registered and do not return data. The runtime catalog is SQLite under `data/catalog`. `database/migrations/001_agent_framework.sql` is the PostGIS schema for a server that has PostGIS installed.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r geospatial\requirements.txt
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m pytest tests -m integration
cd apps/web && npm run build
```

## Documentation

- [Milestone Phase 1–2 report](docs/MILESTONE-PHASE-1-2.md)
- [3D rendering diagnosis & overhaul notes](docs/RENDERING-DIAGNOSIS.md)
- [Unreal / physics integration plan](docs/UNREAL-INTEGRATION.md)
- Master development instructions (project charter)

## License and attribution

OpenStreetMap data © OpenStreetMap contributors (ODbL). Retain attribution for all third-party layers.
