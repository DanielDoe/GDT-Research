#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== GDT full reconstruction pipeline (OSM2World + LOD2 catalog + terrain + exports) =="

& (Join-Path $Root "scripts\run_osm2world_pipeline.ps1")

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  python -m venv .venv
  & $venvPython -m pip install -q -r geospatial\requirements.txt
}

Write-Host "== LOD2 catalog enrichment (USGS EPQS) =="
& $venvPython geospatial\export\enrich_building_catalog_lod2.py --delay 0.035

Write-Host "== Demo district heightmap =="
& $venvPython geospatial\terrain\build_demo_heightmap.py

Write-Host "== Simulation geometry export =="
& $venvPython geospatial\export\simulation_geometry.py

Write-Host "== Geometry audit =="
& $venvPython geospatial\validation\audit_geometry.py

Write-Host "Full pipeline complete."
