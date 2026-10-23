import type { BuildingCatalog } from "@/lib/building-catalog";
import { facadeColor, roofColor } from "@/lib/cesium/procedural-materials";

const ENTITY_PREFIX = "gdt-catalog-bldg-";

function buildingIdFromEntityKey(entityKey: string): string {
  return entityKey.startsWith(ENTITY_PREFIX)
    ? entityKey.slice(ENTITY_PREFIX.length).replace(/-roof$/, "")
    : entityKey;
}

export type CatalogBuildingLayerOptions = {
  show: boolean;
  hiddenBuildingIds: Set<string>;
  debugGeometry: boolean;
  demoDistrictOnly: boolean;
  useEpqsGroundElevation: boolean;
};

export function syncCatalogBuildingVolumes(
  Cesium: typeof import("cesium"),
  viewer: import("cesium").Viewer,
  catalog: BuildingCatalog | null,
  options: CatalogBuildingLayerOptions,
  entityIndex: Map<string, import("cesium").Entity>,
) {
  if (!catalog || !options.show) {
    for (const [id, entity] of entityIndex) {
      viewer.entities.remove(entity);
      entityIndex.delete(id);
    }
    return;
  }

  const want = new Set<string>();
  for (const building of catalog.buildings) {
    if (options.demoDistrictOnly && !building.in_demo_district) continue;
    if (options.hiddenBuildingIds.has(building.id)) continue;
    want.add(building.id);
  }

  for (const [id, entity] of [...entityIndex]) {
    const buildingId = buildingIdFromEntityKey(id);
    if (!want.has(buildingId)) {
      viewer.entities.remove(entity);
      entityIndex.delete(id);
    }
  }

  for (const building of catalog.buildings) {
    if (options.demoDistrictOnly && !building.in_demo_district) continue;
    if (options.hiddenBuildingIds.has(building.id)) continue;

    const entityId = `${ENTITY_PREFIX}${building.id}`;
    const roofId = `${entityId}-roof`;

    const ring = building.footprint_wgs84.flat();
    const salt = building.id.split("").reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
    const roofRise = Math.min(
      building.height_m * 0.42,
      Math.max(0.4, building.roof_rise_m ?? 1.2),
    );
    const wallHeight = Math.max(2.2, building.height_m - roofRise);
    const wallColor = options.debugGeometry
      ? Cesium.Color.fromBytes(120, 180, 255, 210)
      : facadeColor(Cesium, building.facade_material ?? building.building, salt);
    const roofColorValue = options.debugGeometry
      ? Cesium.Color.fromBytes(255, 120, 80, 220)
      : roofColor(Cesium, building.roof_material ?? building.building, salt);

    if (!entityIndex.has(entityId)) {
      const entity = viewer.entities.add({
        id: entityId,
        name: building.name,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
          height: 0,
          extrudedHeight: wallHeight,
          material: new Cesium.ColorMaterialProperty(wallColor),
          outline: options.debugGeometry,
          outlineColor: Cesium.Color.fromBytes(40, 48, 58, 180),
          closeTop: true,
          closeBottom: true,
        },
      });
      entityIndex.set(entityId, entity);
    }

    if (!options.debugGeometry && building.height_m > 3.2 && !entityIndex.has(roofId)) {
      viewer.entities.add({
        id: roofId,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
          height: Math.max(0, wallHeight - 0.05),
          extrudedHeight: building.height_m,
          material: new Cesium.ColorMaterialProperty(roofColorValue),
          outline: false,
        },
      });
      const roofEntity = viewer.entities.getById(roofId);
      if (roofEntity) entityIndex.set(roofId, roofEntity);
    }
  }
}

export function clearCatalogBuildingVolumes(
  viewer: import("cesium").Viewer,
  entityIndex: Map<string, import("cesium").Entity>,
) {
  for (const entity of entityIndex.values()) {
    viewer.entities.remove(entity);
  }
  entityIndex.clear();
  const toRemove = viewer.entities.values.filter((e) =>
    String(e.id).startsWith(ENTITY_PREFIX),
  );
  for (const e of toRemove) {
    viewer.entities.remove(e);
  }
}
