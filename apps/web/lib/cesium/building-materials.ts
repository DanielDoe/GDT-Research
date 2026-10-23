import type { BuildingMaterialMode } from "@/stores/viewer-store";

export function applyBuildingMaterialMode(
  Cesium: typeof import("cesium"),
  model: import("cesium").ModelGraphics | undefined,
  mode: BuildingMaterialMode,
) {
  if (!model) return;

  if (mode === "research") {
    model.color = new Cesium.ConstantProperty(
      Cesium.Color.fromBytes(200, 210, 230, 255),
    );
    model.colorBlendMode = new Cesium.ConstantProperty(Cesium.ColorBlendMode.REPLACE);
    model.silhouetteColor = new Cesium.ConstantProperty(
      Cesium.Color.fromBytes(0, 220, 255, 255),
    );
    model.silhouetteSize = new Cesium.ConstantProperty(1.25);
  } else {
    model.color = new Cesium.ConstantProperty(Cesium.Color.WHITE);
    model.colorBlendMode = new Cesium.ConstantProperty(Cesium.ColorBlendMode.HIGHLIGHT);
    model.silhouetteColor = new Cesium.ConstantProperty(Cesium.Color.TRANSPARENT);
    model.silhouetteSize = new Cesium.ConstantProperty(0);
  }
}

export function applyReconstructionMeshOpacity(
  Cesium: typeof import("cesium"),
  model: import("cesium").ModelGraphics | undefined,
  opacity: number,
  materialMode: BuildingMaterialMode,
) {
  if (!model || materialMode === "research") return;
  const clamped = Math.min(1, Math.max(0.15, opacity));
  if (clamped >= 0.999) {
    model.color = new Cesium.ConstantProperty(Cesium.Color.WHITE);
    model.colorBlendMode = new Cesium.ConstantProperty(Cesium.ColorBlendMode.HIGHLIGHT);
    return;
  }
  model.color = new Cesium.ConstantProperty(Cesium.Color.WHITE.withAlpha(clamped));
  model.colorBlendMode = new Cesium.ConstantProperty(Cesium.ColorBlendMode.MIX);
}
