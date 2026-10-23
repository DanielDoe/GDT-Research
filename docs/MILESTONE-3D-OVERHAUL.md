# Milestone: 3D environment overhaul (Stages A–D)

## Validation performed

| Check | Result |
|--------|--------|
| `npm run build` | Pass |
| `pytest tests/` | Pass (2) |
| Dev server | Pass after `.next` clean |
| Automated browser | **Partial** — Cesium WebGL + tile loading in embedded browser may not match desktop Chrome; use local Chrome for visual sign-off |
| FPS | Shown in-app (~1 s rolling average); not a hardware-certified benchmark |

## What to verify locally (Chrome)

1. Open http://localhost:3000 — default **Downtown 3D perspective** over Esri aerial imagery.
2. Toggle **GDT** vs **Reference OSM Buildings** (requires Ion token in `.env.local`).
3. Presets: aerial, downtown 3D, street-level, harbor, building close-up.
4. Click map near buildings — inspector shows OSM catalog entry + cyan extruded highlight.
5. Click orange **demo UAV** or purple **demo sensor** — inspector updates.
6. **Measure distance** — two clicks; **Pick coordinate** — single click.
7. Layers panel reports GLB loaded and FPS.

## Screenshots

Capture manually after local verification (automated captures in agent temp folder may show global default view if WebGL init is incomplete):

- `docs/screenshots/aerial.png`
- `docs/screenshots/oblique-downtown.png`
- `docs/screenshots/street-level.png`

## Performance note

Target 60 FPS on a workstation is **not guaranteed** with a 6 MB monolithic GLB (~1999 meshes). Next optimization: 3D Tiles + LOD (Stage E).
