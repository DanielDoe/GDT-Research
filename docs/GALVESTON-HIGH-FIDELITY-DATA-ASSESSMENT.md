# Galveston high-fidelity 3D — data availability and feasibility

**Purpose:** Stage 1 findings and demo-block source-data plan for the GDT Research Testbed.  
**Date:** 2026-10-23  
**Status:** Evidence gathered; **no full-city reconstruction committed.** Next engineering work is gated on coverage verification (Google) and LiDAR height pipeline (independent path).

---

## Executive summary

| Path | Can it deliver immersion for downtown Galveston? | Research reuse / simulation geometry | Recommendation |
|------|--------------------------------------------------|--------------------------------------|----------------|
| **A. Google Photorealistic 3D Tiles** | **Unknown for Galveston until empirically tested** (Houston metro is often covered; island cities frequently partial or absent) | **No** — stream-only; Map Tiles policies prohibit extraction, redistribution, and derivative 3D models | Optional **preview layer** after key-based coverage test; not the primary twin |
| **B. Cesium ion (OSM Buildings + World Terrain)** | **Yes for coarse 3D** — untextured boxes, global OSM heights | **No** for textured mesh; styling/metadata only | Reference / comparison only; hide when photorealistic or GDT LOD2+ is active |
| **C. Independent reconstruction (GIS + LiDAR + OSM)** | **Yes for LOD2** — measured footprints, LiDAR heights, procedural materials; **not** window-level photorealism without separate imagery licensing | **Yes** — footprints, prisms, future mesh colliders under our license terms | **Primary path** for the research digital twin |
| **D. Commercial photogrammetry (Nearmap, Vexcel, EagleView, etc.)** | Potentially **yes** if vendor has coastal Texas capture | Contract-dependent; often **no** free redistribution | Quote only if grant/budget allows; document license before integration |
| **E. Self photogrammetry from orthophotos** | Possible for **demo block** only with sufficient overlap and legal imagery | **Yes** if source imagery license permits derivative meshes | Phase F stretch goal; not city-wide |

**Why the app still looks crude (your screenshot):** The visible mass is **OSM2World LOD1** — one monolithic GLB with procedural wall/roof colors and **opaque ground/road meshes** baked into the export. Satellite is **2D imagery draped on the ellipsoid**, not facade texture. Toggling **catalog LOD2 volumes** or lowering **mesh opacity** helps but does not replace measured heights or photorealistic meshes.

**Immediate next step (before more UI work):**

1. Run **Google coverage probe** at downtown coordinates (see §1.1) with a Maps Platform API key.
2. Start **2018 Coastal Texas LiDAR** ingest for `config/demo_district.json` bbox only.
3. Pull **City of Galveston building footprints** for the same bbox and reconcile with OSM/`buildings-catalog.json`.

---

## Demo block definition (Phase F)

From `config/demo_district.json`:

| Field | Value |
|-------|--------|
| Bbox (WGS84) | W −94.7972, S 29.3006, E −94.7948, N 29.3022 |
| Target LOD | LOD2 |
| Municipal footprints in bbox (live query) | **16** polygons ([ArcGIS REST](https://gis.galvestontx.gov/server/rest/services/Basemap/Streets_3D_Basemap/MapServer/0)) |
| Catalog buildings in study area | **566** footprints (full study bbox; **12** flagged `in_demo_district` in enriched catalog) |

This block is the right size for validating alignment, heights, materials, and collision exports before scaling.

---

## Stage 1 — Photorealistic and commercial 3D candidates

### 1.1 Google Photorealistic 3D Tiles (Map Tiles API)

| Criterion | Assessment |
|-----------|------------|
| **Galveston coverage** | **Not confirmed in public docs by city name.** Google publishes a [Photorealistic 3D Maps coverage map](https://developers.google.com/maps/documentation/javascript/3d/coverage) (search “Galveston, TX”). US country row shows Map Tiles 3D availability at country level, but **3D surface geometry is only where the coverage map is blue**. Treat Galveston as **unverified** until tiles load at ~29.301°N, −94.796°W. |
| **Visual quality** | High where present — textured mesh + trees + bridges; same family as Google Earth. |
| **Geographic accuracy** | Generally good for visualization; not survey-grade; datum WGS84. |
| **Licensing** | [Map Tiles API Policies](https://developers.google.com/maps/documentation/tile/policies) — **no downloading, caching beyond session rules, scraping, or creating persistent derivative 3D assets.** Research reuse of mesh geometry **not permitted**. |
| **API** | Enable Map Tiles API, billing account, API key; root URL `https://tile.googleapis.com/v1/3dtiles/root.json?key=…` or `Cesium.createGooglePhotorealistic3DTileset()` with ion + Google linkage ([Cesium guide](https://cesium.com/learn/cesiumjs-learn/cesiumjs-photorealistic-3d-tiles)). |
| **Cost** | Pay-as-you-go Maps Platform; root tileset quota **10,000/day** (May 2024). Session ~3h per root request. |
| **Download** | **No** |
| **Modify** | **No** (stream-only) |
| **Collision geometry** | **Not provided** as separate colliders; would require unauthorized extraction — **out of scope**. |
| **Independent research reuse** | **No** for mesh data; attribution on screen required (`showCreditsOnScreen: true`). |

**Coverage probe (run once `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` or server key exists):**

```text
1. Open Google Maps (Web) → Galveston Strand / 22nd St → enable 3D / tilt.
   If buildings stay flat extrusions, photorealistic mesh is likely absent.
2. In Cesium Sandcastle: load Photorealistic 3D Tiles, fly to demo bbox, check tile count / bounding volume depth.
3. Log: tileset.ready, tiles loaded, and whether building roofs show photographic texture vs flat extrusion.
```

Record results in `docs/coverage-probe-log.md` (create when probe runs).

---

### 1.2 Cesium ion — Google Photorealistic 3D Tiles (wrapper)

Same content and restrictions as §1.1. Ion adds streaming quotas by account tier ([Cesium ion pricing](https://cesium.com/platform/cesium-ion/pricing/)). **Does not change licensing.**

**Cesium OSM Buildings** ([product page](https://cesium.com/platform/cesium-ion/content/cesium-osm-buildings)):

| Criterion | Assessment |
|-----------|------------|
| **Galveston coverage** | Global — includes Galveston |
| **Visual quality** | Untextured extrusions; metadata-rich; **not photorealistic** |
| **License** | Cesium ion ToS; stream-only |
| **Collision** | No official collider mesh |
| **Research reuse** | No mesh export via ion; use our own extrusion exports instead |

**Cesium World Terrain:** Useful for alignment when ion token set; not building geometry.

---

### 1.3 Publicly available textured city meshes

| Source | Galveston? | Notes |
|--------|------------|--------|
| **OpenStreetMap 3D / community GLBs** | Sparse | No city-wide textured mesh for Galveston in repo |
| **Microsoft/USGS city models** | No Galveston-specific release found | National programs focus on other metros |
| **NYC / SF sample ion assets** | N/A | Not geographically applicable |

**Conclusion:** No credible **free, city-wide, textured** Galveston mesh was identified. Do not scrape Google Earth or Street View.

---

### 1.4 Licensed commercial photogrammetry

| Vendor type | Expected coverage | Typical license | Cost |
|-------------|-------------------|-----------------|------|
| **Aerial oblique / mesh vendors** (Nearmap, Vexcel, EagleView, Hexagon) | Must request **coastal Texas** footprint | Often **viewer/API only**; redistribution prohibited | **$$$** — tile or AOI quotes |
| **Municipal contracted meshes** | Unknown without public records request | May be **internal use only** | N/A until FOIA/portal search |

**Action:** If photorealistic preview fails (§1.1), request **AOI quote** for demo bbox only before any integration.

---

### 1.5 Locally reconstructable imagery

| Dataset | Coverage | License / access | Use for LOD2/LOD3 |
|---------|----------|------------------|-------------------|
| **City of Galveston Aerials 2026** | City ([image server](https://gis.galvestontx.gov/image/rest/services/Aerials_2026/MapServer)) | **Verify** city GIS terms before derivative mesh/texturing | Ortho **drape** on LiDAR roofs (LOD2.5); full facade texturing needs oblique or ML facade libs + legal review |
| **ArcGIS World Imagery** (current basemap) | Global | Esri terms — **not** for unconstrained ML training / redistribution | Basemap only |
| **NOAA / USGS ortho** | Regional mosaics | Generally more permissive for research | Terrain/roof color sampling with attribution |

Photogrammetry from nadir ortho alone **does not** recover vertical facades; set expectations accordingly.

---

### 1.6 LiDAR and elevation (independent path — **strong for Galveston**)

| Dataset | Year | Extent | Quality | Access | Research reuse |
|---------|------|--------|---------|--------|----------------|
| **2018 TWDB Coastal Texas LiDAR** | 2018 | **Galveston County / coast** incl. H-GAC partners | ≤0.5 m NPS, ~10 cm RMSEz (non-veg) | [NOAA AWS LAZ 8898](https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/laz/geoid18/8898/index.html), [DEM 8899](https://coast.noaa.gov/htdata/raster2/elevation/TX_Coastal_DEM_2018_8899/), [TNRIS Upper Coast 2018](https://data.tnris.org/?category=Lidar) | **Yes** — public federal/state distribution; cite metadata |
| **2006 TWDB Galveston County LiDAR** | 2006 | County | 1.4 m GSD; aging | NOAA Digital Coast | Yes, but superseded by 2018 for buildings |
| **USGS 3DEP / EPQS** | Continuous | Point queries | Good for **ground**; not building height | EPQS API (already in catalog enrich script) | Yes |
| **NOAA coastal DEMs / VDatum** | Various | Tide/coast | Critical for coastal flooding research | NOAA | Yes |

**2018 deliverables (H-GAC):** LAS 1.4, hydro-flattened DEM, breaklines, **building footprint data** (vendor-derived), contours — see [H-GAC LiDAR page](https://www.h-gac.com/imagery/lidar) (paid tile download for full extent; NOAA subset may suffice for demo bbox).

**Building height method (demo block):** For each footprint polygon, compute **p95 − ground** (class 2/ground) from LAZ points inside polygon; flag outliers vs OSM `height`/`levels`. No facade texture implied.

---

### 1.7 Building footprints and attributes

| Source | Records | Fields | Access | Match to GDT |
|--------|---------|--------|--------|--------------|
| **City of Galveston — Building Footprints** | Citywide layer (query paginated) | `XREF`, `DISTRICT`, `STATUS`, geometry | [MapServer/0](https://gis.galvestontx.gov/server/rest/services/Basemap/Streets_3D_Basemap/MapServer/0) GeoJSON/PBF | **Authoritative footprints** for demo block |
| **OpenStreetMap** | Study extract | `building`, `height`, `levels`, names | Already in pipeline / catalog | Cross-walk via spatial join |
| **GDT buildings-catalog.json** | 566 | EPQS ground, materials, demo flags | Repo | Merge keys: `osm_id` + municipal `XREF` |

---

## Stage 2 — Photorealistic preview (conditional)

**Proceed only if §1.1 probe shows textured mesh at demo bbox.**

Planned app behavior (not implemented in this document pass):

- New visualization mode: **Photorealistic 3D**
- Load Google tileset via ion or direct API key
- **Auto-hide** OSM2World GLB + catalog extrusions in that mode (or clip to outside photorealistic extent)
- Keep **satellite basemap off** or minimal per Google examples; globe optional
- **Attribution** on screen; no offline cache
- Optional: Cesium globe + World Terrain for areas outside Google mesh

**If probe fails:** Skip Stage 2; document “no authorized photorealistic stream for downtown Galveston” and invest in Stage 3–5.

---

## Stage 3–5 — Independent reconstruction (recommended primary)

### Priority order for demo block

1. **Footprints:** Municipal GIS ⊕ OSM consensus (snap vertices, preserve both IDs).
2. **Ground Z:** 2018 DEM sample at footprint centroid (NAVD88, document GEOID18).
3. **Height:** 2018 LiDAR p95 inside footprint; fallback OSM `height` / `levels×3 m` / 10 m default.
4. **Roof:** LOD2 — flat or OSM `roof:shape` simplified mesh; no dormers without data.
5. **Materials:** Procedural by building type (already started); **decouple debug colors** from production mode.
6. **Roads:** Separate road surface mesh or imagery-only — **do not** use opaque black OSM2World road planes in normal mode.
7. **Collision:** Extruded prisms → GeoJSON (existing script); upgrade to simplified mesh when heights are LiDAR-backed.
8. **Validation:** RMSE of roof Z vs LiDAR p95; footprint IoU municipal vs OSM; visual checklist at street camera.

### Full city

**Deferred** until demo block metrics meet targets in `docs/IMMERSIVE-3D-ROADMAP.md`.

---

## Stage 4 — Visual environment (scope note)

Current OSM2World export drives **red/yellow** appearance and **black roads**. Fixing immersion requires:

- Default **hide or high-transparency** ground/road GLB submeshes (UI slider exists; should be default for “Research 3D”).
- **LiDAR-backed LOD2** catalog layer as primary building source when `buildingSourceMode = gdt_catalog_lod2`.
- Separate **debug geometry** styling (already partially wired).

This is **geometry and pipeline work**, not a palette tweak.

---

## Stage 6–8 — Interaction, Unreal, comparison

- **Stage 6:** Walk collision remains blocked until colliders exist; prioritize demo-block mesh/prisms.
- **Stage 7:** See `docs/UNREAL-INTEGRATION.md` — same GeoJSON + future GLB tiles.
- **Stage 8:** Screenshot matrix after (1) LOD1 today, (2) LOD2 demo block, (3) photorealistic probe if any, (4) street-level walk — label each layer as **mesh / imagery / estimate**.

---

## Risk register

| Risk | Mitigation |
|------|------------|
| Google mesh absent on Galveston Island | Plan B = LiDAR LOD2 + 2026 ortho roof textures |
| 2018 LiDAR gaps on water’s edge | Use DEM + manual QA on Strand frontage |
| Municipal GIS license silent on derivatives | Request GIS office clarification before texturing |
| Monolithic OSM2World GLB blocks per-building workflow | Split demo block to per-building GLB or 3D Tiles (Phase F export) |
| EPQS-only heights for most catalog | Re-run enrich with LiDAR script (new), not EPQS alone |

---

## References

- Google Photorealistic 3D Tiles: https://developers.google.com/maps/documentation/tile/3d-tiles  
- Google 3D coverage map: https://developers.google.com/maps/documentation/javascript/3d/coverage  
- Cesium photorealistic quickstart: https://cesium.com/learn/cesiumjs-learn/cesiumjs-photorealistic-3d-tiles  
- 2018 Coastal Texas LiDAR metadata: https://www.fisheries.noaa.gov/inport/item/58236  
- Galveston GIS building footprints: https://gis.galvestontx.gov/server/rest/services/Basemap/Streets_3D_Basemap/MapServer/0  
- Project geometry audit: `docs/GEOMETRY-AUDIT.md`  
- Pipeline roadmap: `docs/IMMERSIVE-3D-ROADMAP.md`
