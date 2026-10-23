export type DemoHeightmapPayload = {
  rectangle_wgs84: { west: number; south: number; east: number; north: number };
  width: number;
  height: number;
  heights_m: number[];
};

const HEIGHTMAP_URL = "/assets/galveston/demo-district-heightmap.json";

export async function loadDemoHeightmap(): Promise<DemoHeightmapPayload | null> {
  try {
    const res = await fetch(HEIGHTMAP_URL);
    if (!res.ok) return null;
    return (await res.json()) as DemoHeightmapPayload;
  } catch {
    return null;
  }
}

/**
 * Demo-only terrain: repeats the district heightmap for requested tiles.
 * Suitable for local exploration over the demo bbox — not global Galveston coverage.
 */
export async function createDemoDistrictTerrainProvider(Cesium: typeof import("cesium")) {
  const payload = await loadDemoHeightmap();
  if (!payload) return null;

  const grid = new Float32Array(payload.heights_m);
  return new Cesium.CustomHeightmapTerrainProvider({
    width: payload.width,
    height: payload.height,
    credit: "USGS EPQS (demo district 16×16 grid)",
    callback: () => grid,
  });
}
