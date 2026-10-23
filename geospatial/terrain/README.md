# Terrain pipeline (Phase B)

Goal: replace ellipsoid-only navigation with **locally accurate elevation** for Galveston’s low-relief coastal grid.

## Intended sources

- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) LiDAR / DEM
- [TNRIS](https://tnris.org/) Texas elevation products
- NOAA coastal DEM where applicable for shoreline experiments

## Processing (planned)

1. Clip DEM to `config/study_area.json` and `config/demo_district.json`.
2. Verify vertical datum (NAVD88) vs WGS84 ellipsoid used by Cesium.
3. Generate Cesium-compatible terrain (quantized mesh via Cesium ion upload, or custom `HeightmapTerrainProvider` for demos).
4. Record RMSE at surveyed benchmarks in `docs/validation/terrain-*.md`.

## Runtime today

The web viewer uses `Cesium.createWorldTerrainAsync()` when `NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN` is set. That is **global** terrain, not the local TNRIS merge.

Do not claim flood or mobility accuracy until local DEM is integrated and validated.
