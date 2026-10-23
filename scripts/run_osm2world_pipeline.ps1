#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== GDT OSM2World pipeline =="

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  python -m venv .venv
  & $venvPython -m pip install -q -r geospatial\requirements.txt
}

& $venvPython geospatial\acquisition\download_osm_study_area.py
& $venvPython geospatial\osm2world\ensure_osm2world.py

$java = Join-Path $Root "geospatial\osm2world\jre\bin\java.exe"
if (-not (Test-Path $java)) {
  & $venvPython (Join-Path $Root "geospatial\osm2world\ensure_portable_jre.py")
  $java = Join-Path $Root "geospatial\osm2world\jre\bin\java.exe"
}

$jar = Join-Path $Root "geospatial\osm2world\bin\OSM2World.jar"
$osm = Join-Path $Root "data\processed\osm\galveston-study.osm"
$outDir = Join-Path $Root "assets\buildings\osm2world"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$glbOut = Join-Path $outDir "galveston-study.glb"
$props = Join-Path $Root "geospatial\osm2world\osm2world.properties"

& $java `
  --add-exports java.base/java.lang=ALL-UNNAMED `
  --add-exports java.desktop/sun.awt=ALL-UNNAMED `
  --add-exports java.desktop/sun.java2d=ALL-UNNAMED `
  -Xmx2G `
  -jar $jar `
  -i $osm `
  -o $glbOut `
  --config $props

if (-not (Test-Path $glbOut)) { throw "OSM2World did not produce $glbOut" }

& $venvPython geospatial\osm2world\export_glb.py
& $venvPython geospatial\export\osm_building_catalog.py
Write-Host "Pipeline complete: $glbOut"
