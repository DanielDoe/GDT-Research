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
}

export interface BuildingCatalog {
  study_area: string;
  count: number;
  default_height_m: number;
  buildings: BuildingCatalogEntry[];
}

const CATALOG_URL = "/assets/galveston/buildings-catalog.json";

export async function loadBuildingCatalog(): Promise<BuildingCatalog | null> {
  try {
    const res = await fetch(CATALOG_URL);
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
): BuildingCatalogEntry | null {
  let best: BuildingCatalogEntry | null = null;
  let bestDist = maxDistanceM;
  const latRad = (latitude * Math.PI) / 180;
  const mPerDegLat = 111_320;
  const mPerDegLon = 111_320 * Math.cos(latRad);

  for (const b of catalog.buildings) {
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
