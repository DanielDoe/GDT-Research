import { create } from "zustand";
import type { CameraPresetKey } from "@/lib/study-area";
import {
  imagerySourceLabel,
  type SatelliteImageryKind,
} from "@/lib/cesium/imagery-providers";

export type BuildingSourceMode =
  | "reference_osm"
  | "gdt_reconstructed"
  | "gdt_catalog_lod2"
  | "none";
export type MapMode = "satellite" | "street" | "hybrid" | "terrain_3d" | "research_3d";
/** @deprecated Use MapMode */
export type ImageryMode = MapMode;
export type ViewSceneMode = "3d" | "2d";
export type InteractionTool = "navigate" | "measure" | "pick_coordinate";
export type BuildingMaterialMode = "realistic" | "research";

/** Controls satellite vs 3D building composition (independent of basemap map mode). */
export type SceneVisualizationMode =
  | "satellite_only"
  | "satellite_plus_3d"
  | "research_geometry"
  | "high_fidelity";

export type NavigationMode = "orbit" | "fly" | "walk";

export type GeometryLodLevel = "LOD1" | "LOD2" | "LOD3";

export interface LayerVisibility {
  terrain: boolean;
  imagery: boolean;
  referenceBuildings: boolean;
  reconstructedBuildings: boolean;
  roads: boolean;
  buildingFootprints: boolean;
  buildingIdentifiers: boolean;
  placeNames: boolean;
  landmarks: boolean;
  water: boolean;
  vegetation: boolean;
  geographicCoordinates: boolean;
  researchAssets: boolean;
  infrastructure: boolean;
  customAssets: boolean;
  catalogVolumes: boolean;
  localDemoTerrain: boolean;
}

export interface ViewerStatus {
  ionTokenPresent: boolean;
  arcGisTokenPresent: boolean;
  terrainSource: "cesium_world" | "ellipsoid" | "demo_epqs_heightmap";
  imagerySource: string;
  satelliteImageryKind: SatelliteImageryKind | null;
  satelliteImageryDetail: string | null;
  imageryLoading: boolean;
  reconstructedAssetLoaded: boolean;
  reconstructedAssetUrl: string | null;
  loadingMessage: string | null;
  errorMessage: string | null;
  measuredDistance_m: number | null;
  pickedCoordinate: { latitude: number; longitude: number; height_m: number } | null;
  fpsEstimate: number | null;
}

export interface SelectedObjectInfo {
  kind: "building" | "road" | "simulation" | "observation" | "unknown";
  id: string;
  label?: string;
  latitude?: number;
  longitude?: number;
  height_m?: number;
  footprint_area_m2?: number;
  elevation_m?: number;
  classification?: string;
  data_source?: string;
  quality?: string;
  extra?: Record<string, string | number | boolean | null>;
}

export interface ViewerState {
  buildingSourceMode: BuildingSourceMode;
  mapMode: MapMode;
  /** @deprecated alias for mapMode */
  imageryMode: MapMode;
  buildingMaterialMode: BuildingMaterialMode;
  viewSceneMode: ViewSceneMode;
  interactionTool: InteractionTool;
  layers: LayerVisibility;
  proceduralGroundVisible: boolean;
  reconstructionMeshOpacity: number;
  terrainExaggerationEnabled: boolean;
  terrainExaggeration: number;
  status: ViewerStatus;
  selectedObject: SelectedObjectInfo | null;
  activeScene: string;
  cameraPreset: CameraPresetKey;
  cameraPresetEpoch: number;
  orbitSelectedBuilding: boolean;
  cameraHud: {
    longitude: number;
    latitude: number;
    height_m: number;
    heading_deg: number;
    pitch_deg: number;
  } | null;
  savedViews: Array<{
    id: string;
    name: string;
    longitude: number;
    latitude: number;
    height_m: number;
    heading_deg: number;
    pitch_deg: number;
  }>;
  layersPanelOpen: boolean;
  inspectorPanelOpen: boolean;
  mapStyleSelectorOpen: boolean;
  sceneVisualization: SceneVisualizationMode;
  navigationMode: NavigationMode;
  activeGeometryLod: GeometryLodLevel;
  hiddenBuildingIds: string[];
  walkMoveSpeedMps: number;
  walkEyeHeightM: number;
  setLayersPanelOpen: (open: boolean) => void;
  setInspectorPanelOpen: (open: boolean) => void;
  setMapStyleSelectorOpen: (open: boolean) => void;
  setBuildingSourceMode: (mode: BuildingSourceMode) => void;
  setMapMode: (mode: MapMode) => void;
  /** @deprecated Use setMapMode */
  setImageryMode: (mode: MapMode) => void;
  setBuildingMaterialMode: (mode: BuildingMaterialMode) => void;
  setViewSceneMode: (mode: ViewSceneMode) => void;
  setInteractionTool: (tool: InteractionTool) => void;
  setLayer: (key: keyof LayerVisibility, visible: boolean) => void;
  setProceduralGroundVisible: (visible: boolean) => void;
  setReconstructionMeshOpacity: (opacity: number) => void;
  setTerrainExaggerationEnabled: (enabled: boolean) => void;
  setTerrainExaggeration: (value: number) => void;
  setStatus: (partial: Partial<ViewerStatus>) => void;
  setSelectedObject: (obj: SelectedObjectInfo | null) => void;
  setActiveScene: (scene: string) => void;
  setCameraPreset: (preset: CameraPresetKey) => void;
  flyToSelectedBuilding: () => void;
  setOrbitSelectedBuilding: (on: boolean) => void;
  setCameraHud: (hud: ViewerState["cameraHud"]) => void;
  addSavedView: (view: ViewerState["savedViews"][number]) => void;
  setSceneVisualization: (mode: SceneVisualizationMode) => void;
  setNavigationMode: (mode: NavigationMode) => void;
  setWalkMoveSpeedMps: (mps: number) => void;
  setWalkEyeHeightM: (m: number) => void;
  hideBuilding: (id: string) => void;
  showBuilding: (id: string) => void;
  clearHiddenBuildings: () => void;
  restoreSceneModifications: (hiddenIds: string[]) => void;
}

const defaultLayers: LayerVisibility = {
  terrain: true,
  imagery: true,
  referenceBuildings: false,
  reconstructedBuildings: false,
  roads: true,
  buildingFootprints: false,
  buildingIdentifiers: false,
  placeNames: true,
  landmarks: false,
  water: false,
  vegetation: false,
  geographicCoordinates: false,
  researchAssets: true,
  infrastructure: false,
  customAssets: true,
  catalogVolumes: true,
  localDemoTerrain: false,
};

export const useViewerStore = create<ViewerState>((set, get) => ({
  buildingSourceMode: "gdt_catalog_lod2",
  mapMode: "hybrid",
  imageryMode: "hybrid",
  buildingMaterialMode: "realistic",
  viewSceneMode: "3d",
  interactionTool: "navigate",
  layers: defaultLayers,
  proceduralGroundVisible: false,
  reconstructionMeshOpacity: 1,
  terrainExaggerationEnabled: false,
  terrainExaggeration: 1.75,
  layersPanelOpen: true,
  inspectorPanelOpen: true,
  mapStyleSelectorOpen: false,
  sceneVisualization: "satellite_plus_3d",
  navigationMode: "orbit",
  activeGeometryLod: "LOD2",
  hiddenBuildingIds: [],
  walkMoveSpeedMps: 3.2,
  walkEyeHeightM: 1.65,
  status: {
    ionTokenPresent: Boolean(
      (process.env.NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN ?? "").trim(),
    ),
    arcGisTokenPresent: Boolean(
      (process.env.NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN ?? "").trim(),
    ),
    terrainSource: "ellipsoid",
    imagerySource: "arcgis_world_imagery",
    satelliteImageryKind: null,
    satelliteImageryDetail: null,
    imageryLoading: false,
    reconstructedAssetLoaded: false,
    reconstructedAssetUrl: null,
    loadingMessage: null,
    errorMessage: null,
    measuredDistance_m: null,
    pickedCoordinate: null,
    fpsEstimate: null,
  },
  selectedObject: null,
  activeScene: "Downtown Galveston demonstration",
  cameraPreset: "downtown_3d",
  cameraPresetEpoch: 0,
  orbitSelectedBuilding: false,
  cameraHud: null,
  savedViews: [],
  setLayersPanelOpen: (open) => set({ layersPanelOpen: open }),
  setInspectorPanelOpen: (open) => set({ inspectorPanelOpen: open }),
  setMapStyleSelectorOpen: (open) => set({ mapStyleSelectorOpen: open }),
  setBuildingSourceMode: (mode) =>
    set((state) => ({
      buildingSourceMode: mode,
      layers: {
        ...state.layers,
        referenceBuildings: mode === "reference_osm",
        reconstructedBuildings: mode === "gdt_reconstructed",
        catalogVolumes: mode === "gdt_catalog_lod2",
      },
      activeGeometryLod: mode === "gdt_catalog_lod2" ? "LOD2" : mode === "gdt_reconstructed" ? "LOD1" : state.activeGeometryLod,
    })),
  setMapMode: (mode) => {
    const satelliteKind = get().status.satelliteImageryKind;
    const showBuildings = mode !== "satellite";
    const photo = mode === "satellite" || mode === "street" || mode === "hybrid";
    set((state) => ({
      mapMode: mode,
      imageryMode: mode,
      buildingSourceMode: showBuildings ? ("gdt_catalog_lod2" as const) : ("none" as const),
      buildingMaterialMode: mode === "research_3d" ? ("research" as const) : ("realistic" as const),
      sceneVisualization:
        mode === "satellite"
          ? ("satellite_only" as const)
          : mode === "research_3d"
            ? ("research_geometry" as const)
            : ("satellite_plus_3d" as const),
      terrainExaggerationEnabled: mode === "terrain_3d",
      terrainExaggeration: mode === "terrain_3d" ? 3 : state.terrainExaggeration,
      activeGeometryLod: showBuildings ? ("LOD2" as const) : state.activeGeometryLod,
      layers: {
        ...state.layers,
        imagery: photo,
        terrain: true,
        catalogVolumes: showBuildings,
        reconstructedBuildings: false,
        referenceBuildings: false,
        placeNames: mode === "hybrid" || mode === "street",
        roads: mode === "hybrid",
        localDemoTerrain: false,
      },
      status: {
        ...state.status,
        imagerySource: imagerySourceLabel(mode, satelliteKind),
        imageryLoading: photo,
      },
    }));
    window.setTimeout(() => {
      set((state) => ({
        status: { ...state.status, imageryLoading: false },
      }));
    }, 650);
  },
  setImageryMode: (mode) => get().setMapMode(mode),
  setBuildingMaterialMode: (mode) => set({ buildingMaterialMode: mode }),
  setViewSceneMode: (mode) => set({ viewSceneMode: mode }),
  setInteractionTool: (tool) =>
    set((state) => ({
      interactionTool: tool,
      status: {
        ...state.status,
        measuredDistance_m: tool === "measure" ? state.status.measuredDistance_m : null,
        pickedCoordinate: tool === "pick_coordinate" ? state.status.pickedCoordinate : null,
      },
    })),
  setLayer: (key, visible) =>
    set((state) => ({
      layers: { ...state.layers, [key]: visible },
    })),
  setProceduralGroundVisible: (visible) => set({ proceduralGroundVisible: visible }),
  setReconstructionMeshOpacity: (opacity) =>
    set({ reconstructionMeshOpacity: Math.min(1, Math.max(0.2, opacity)) }),
  setTerrainExaggerationEnabled: (enabled) => set({ terrainExaggerationEnabled: enabled }),
  setTerrainExaggeration: (value) =>
    set({ terrainExaggeration: Math.min(4, Math.max(1, value)) }),
  setStatus: (partial) =>
    set((state) => ({
      status: { ...state.status, ...partial },
    })),
  setSelectedObject: (obj) => set({ selectedObject: obj }),
  setActiveScene: (scene) => set({ activeScene: scene }),
  setCameraPreset: (preset) =>
    set((state) => ({
      cameraPreset: preset,
      cameraPresetEpoch: state.cameraPresetEpoch + 1,
    })),
  flyToSelectedBuilding: () =>
    set((state) => ({
      cameraPreset: "building_closeup",
      cameraPresetEpoch: state.cameraPresetEpoch + 1,
      orbitSelectedBuilding: true,
    })),
  setOrbitSelectedBuilding: (on) => set({ orbitSelectedBuilding: on }),
  setCameraHud: (hud) => set({ cameraHud: hud }),
  addSavedView: (view) =>
    set((state) => ({ savedViews: [...state.savedViews, view] })),
  setSceneVisualization: (mode) =>
    set((state) => {
      if (mode === "satellite_only") {
        return {
          sceneVisualization: mode,
          buildingSourceMode: "none" as const,
          layers: {
            ...state.layers,
            reconstructedBuildings: false,
            catalogVolumes: false,
          },
        };
      }
      if (mode === "high_fidelity") {
        return {
          sceneVisualization: mode,
          buildingSourceMode: "gdt_catalog_lod2" as const,
          layers: {
            ...state.layers,
            reconstructedBuildings: false,
            catalogVolumes: true,
            localDemoTerrain: false,
            terrain: true,
          },
          activeGeometryLod: "LOD2" as const,
        };
      }
      return {
        sceneVisualization: mode,
        buildingSourceMode:
          state.buildingSourceMode === "none" ? ("gdt_catalog_lod2" as const) : state.buildingSourceMode,
        layers: {
          ...state.layers,
          reconstructedBuildings:
            state.buildingSourceMode === "gdt_reconstructed",
          catalogVolumes:
            state.buildingSourceMode === "none" || state.buildingSourceMode === "gdt_catalog_lod2",
        },
        buildingMaterialMode: mode === "research_geometry" ? ("research" as const) : state.buildingMaterialMode,
        activeGeometryLod: mode === "research_geometry" ? ("LOD1" as const) : ("LOD2" as const),
      };
    }),
  setNavigationMode: (mode) => set({ navigationMode: mode }),
  setWalkMoveSpeedMps: (mps) =>
    set({ walkMoveSpeedMps: Math.min(25, Math.max(0.5, mps)) }),
  setWalkEyeHeightM: (m) => set({ walkEyeHeightM: Math.min(50, Math.max(0.5, m)) }),
  hideBuilding: (id) =>
    set((state) => ({
      hiddenBuildingIds: state.hiddenBuildingIds.includes(id)
        ? state.hiddenBuildingIds
        : [...state.hiddenBuildingIds, id],
    })),
  showBuilding: (id) =>
    set((state) => ({
      hiddenBuildingIds: state.hiddenBuildingIds.filter((x) => x !== id),
    })),
  clearHiddenBuildings: () => set({ hiddenBuildingIds: [] }),
  restoreSceneModifications: (hiddenIds) => set({ hiddenBuildingIds: hiddenIds }),
}));
