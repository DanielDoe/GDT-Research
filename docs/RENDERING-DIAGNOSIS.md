# GDT rendering diagnosis (root causes)

Date: 2026-10-23. Scope: downtown Galveston demonstration viewer (`apps/web`).

## Summary

The dashboard was functional, but the scene read as a **flat map** because of a combination of **imagery choice**, **missing Ion services**, **camera scale vs. building height**, and **asset packaging** — not because Cesium was stuck in 2D.

## Findings

| # | Check | Result |
|---|--------|--------|
| 1 | `SCENE3D` | **Yes** — `scene3DOnly` was true; globe renders in 3D. |
| 2 | Camera angle | Mixed — presets included oblique views, but default height (~180–320 m) over a **~4.5 km** model made extruded mesh appear as a thin skin on OSM tiles. |
| 3 | Cesium World Terrain | **Usually off** — requires `NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN`; without it, ellipsoid terrain only. |
| 4 | Imagery | **OSM street tiles were the only base layer** — cartographic, not aerial; reinforces “flat map” perception. |
| 5 | Cesium OSM Buildings | **Only with Ion token** — not created when token missing. |
| 6 | Ion token | Often **unset in local dev** — terrain + reference buildings unavailable. |
| 7 | GDT GLB geometry | **Valid** — ~6.1 MB, 1999 meshes, ~88k vertices; horizontal extent ~4.5 km × 2.7 km; vertical extent **0–7.5 m** (OSM2World Y-up). |
| 8 | Georeferencing | Anchor at study centroid (`local_origin_wgs84`); OSM2World origin matches config — **correct in principle**; fine tuning via `galveston-demo.transform.json`. |
| 9 | Placement / scale | Single entity at anchor — not underground; **visually lost** when camera too high or imagery lacks vertical cues. |
| 10 | Layers | GDT vs reference modes were wired, but **both could not be compared fairly** without Ion. |
| 11 | React / Cesium lifecycle | **postRender updated Zustand every frame** → unnecessary React work and stutter risk. |
| 12 | Network / WebGL | GLB HEAD/load succeeds; prior bug was **async load after viewer destroy** (fixed). |

## Primary root causes

1. **Street-map imagery as the only base layer** (no aerial/satellite context).
2. **No Ion token** → no world terrain, no Cesium OSM Buildings reference layer.
3. **Camera altitude too high** relative to ~7.5 m mesh heights for a city-wide GLB.
4. **Monolithic GLB** — no per-building picking; metadata was a single placeholder entry.
5. **Per-frame HUD state updates** — performance / smoothness impact.

## Remediation implemented (Stages A–D)

- Default **Esri World Imagery** (with OSM optional overlay); documented licensing.
- Oblique **default camera** (`downtown_3d`), street-level and harbor presets.
- **2D/3D toggle** (3D default), smooth camera controller tuning, collision detection.
- **566-building OSM catalog** for selection, highlight extrusions, inspector metadata.
- **Throttled HUD** + **FPS estimate** in status panel.
- **Demo simulation objects** (UAV + sensor) with inspector-driven transforms.
- Measure distance + pick coordinate tools.

## Remaining gaps (Stage E+)

- Split city geometry into **3D Tiles** / per-building assets for LOD and picking on mesh.
- LiDAR terrain (TNRIS / 3DEP) and height refinement in OSM2World / Blender pipeline.
- Per-building mesh IDs in export (not only footprint catalog).
- Validated alignment report vs reference imagery.
