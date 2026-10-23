import type { BuildingMaterialMode, SceneVisualizationMode } from "@/stores/viewer-store";

export function resolveBuildingMaterial(
  visualization: SceneVisualizationMode,
  explicit: BuildingMaterialMode,
): BuildingMaterialMode {
  if (visualization === "research_geometry") return "research";
  if (visualization === "high_fidelity") return "realistic";
  return explicit;
}

export function shouldShowGeneratedBuildings(visualization: SceneVisualizationMode): boolean {
  return visualization !== "satellite_only";
}

export function reconstructionOpacityForVisualization(
  visualization: SceneVisualizationMode,
  proceduralGroundVisible: boolean,
  meshOpacity: number,
): number {
  if (visualization === "research_geometry") {
    return proceduralGroundVisible ? Math.min(meshOpacity, 0.92) : 0.4;
  }
  if (visualization === "satellite_only") return 0;
  return proceduralGroundVisible ? meshOpacity : 0.35;
}
