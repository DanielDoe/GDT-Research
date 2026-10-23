export interface BuildingCatalogEntry {
  id: string;
  osm_id: string;
  name: string;
  building: string;
  latitude: number;
  longitude: number;
  height_m: number;
  height_source: string;
  footprint_area_m2: number;
  footprint_wgs84: number[][];
  source: string;
  lod?: "LOD1" | "LOD2" | "LOD3";
  in_demo_district?: boolean;
  ground_elevation_m?: number | null;
  ground_elevation_source?: string | null;
  ground_elevation_datum?: string | null;
  reconstruction_method?: string;
  quality_class?: string;
  facade_material?: string;
  roof_material?: string;
  roof_rise_m?: number;
  gis_xref?: string;
  collision_ready?: boolean;
  simulation_proxy?: string;
}

export interface BuildingCatalog {
  study_area: string;
  count: number;
  default_height_m: number;
  schema_version?: number;
  lod2_count?: number;
  demo_district?: string;
  elevation_notes?: string;
  buildings: BuildingCatalogEntry[];
}

const CATALOG_URL = "/assets/galveston/buildings-catalog.json";

export async function loadBuildingCatalog(): Promise<BuildingCatalog | null> {
  try {
    const res = await fetch(CATALOG_URL, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as BuildingCatalog;
  } catch {
    return null;
  }
}

/** Nearest-building lookup in WGS84 (good enough for downtown scale). */
export function findNearestBuilding(
  catalog: BuildingCatalog,
  longitude: number,
  latitude: number,
  maxDistanceM = 80,
  excludeIds?: Set<string>,
): BuildingCatalogEntry | null {
  let best: BuildingCatalogEntry | null = null;
  let bestDist = maxDistanceM;
  const latRad = (latitude * Math.PI) / 180;
  const mPerDegLat = 111_320;
  const mPerDegLon = 111_320 * Math.cos(latRad);

  for (const b of catalog.buildings) {
    if (excludeIds?.has(b.id)) continue;
    const dx = (b.longitude - longitude) * mPerDegLon;
    const dy = (b.latitude - latitude) * mPerDegLat;
    const d = Math.hypot(dx, dy);
    if (d < bestDist) {
      bestDist = d;
      best = b;
    }
  }
  return best;
}
