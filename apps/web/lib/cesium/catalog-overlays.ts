import type { BuildingCatalog } from "@/lib/building-catalog";

const FOOTPRINT_PREFIX = "gdt-footprint-";
const ID_LABEL_PREFIX = "gdt-building-id-";

export function syncCatalogOverlays(
  Cesium: typeof import("cesium"),
  viewer: import("cesium").Viewer,
  catalog: BuildingCatalog | null,
  options: {
    showFootprints: boolean;
    showIdentifiers: boolean;
  },
  entityIndex: Map<string, import("cesium").Entity>,
) {
  if (!catalog) return;

  const wantIds = new Set<string>();
  for (const building of catalog.buildings) {
    if (options.showFootprints) {
      wantIds.add(`${FOOTPRINT_PREFIX}${building.id}`);
    }
    if (options.showIdentifiers) {
      wantIds.add(`${ID_LABEL_PREFIX}${building.id}`);
    }
  }

  for (const [id, entity] of entityIndex) {
    if (!wantIds.has(id)) {
      viewer.entities.remove(entity);
      entityIndex.delete(id);
    }
  }

  if (options.showFootprints) {
    for (const building of catalog.buildings) {
      const id = `${FOOTPRINT_PREFIX}${building.id}`;
      if (entityIndex.has(id)) continue;
      const ring = building.footprint_wgs84.flat();
      const entity = viewer.entities.add({
        id,
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
          height: 0,
          extrudedHeight: building.height_m,
          material: Cesium.Color.fromBytes(255, 200, 0, 40),
          outline: true,
          outlineColor: Cesium.Color.fromBytes(255, 220, 80, 180),
        },
      });
      entityIndex.set(id, entity);
    }
  }

  if (options.showIdentifiers) {
    for (const building of catalog.buildings) {
      const id = `${ID_LABEL_PREFIX}${building.id}`;
      if (entityIndex.has(id)) continue;
      const entity = viewer.entities.add({
        id,
        position: Cesium.Cartesian3.fromDegrees(
          building.longitude,
          building.latitude,
          building.height_m + 2,
        ),
        label: {
          text: building.name || building.id,
          font: "10px sans-serif",
          fillColor: Cesium.Color.WHITE,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 2,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.55),
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 2500),
        },
      });
      entityIndex.set(id, entity);
    }
  }
}

export function clearCatalogOverlays(
  viewer: import("cesium").Viewer,
  entityIndex: Map<string, import("cesium").Entity>,
) {
  for (const entity of entityIndex.values()) {
    viewer.entities.remove(entity);
  }
  entityIndex.clear();
}
