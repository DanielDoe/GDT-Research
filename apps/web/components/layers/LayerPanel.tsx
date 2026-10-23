"use client";

import { Layers3 } from "lucide-react";
import { PanelCloseButton } from "@/components/viewer/PanelDock";
import {
  useViewerStore,
  type BuildingMaterialMode,
  type LayerVisibility,
} from "@/stores/viewer-store";

type LayerRow = {
  key: keyof LayerVisibility;
  label: string;
  hint?: string;
  unavailable?: boolean;
};

const layerRows: LayerRow[] = [
  { key: "imagery", label: "Basemap imagery" },
  { key: "terrain", label: "Terrain / globe elevation" },
  { key: "referenceBuildings", label: "Reference OSM buildings (Cesium ion)" },
  { key: "reconstructedBuildings", label: "GDT reconstructed buildings (OSM2World GLB)" },
  { key: "catalogVolumes", label: "GDT city footprints + LiDAR heights (LOD2)" },
  { key: "localDemoTerrain", label: "Local USGS elevation (demo district heightmap)" },
  { key: "buildingFootprints", label: "Building footprints (catalog)" },
  { key: "buildingIdentifiers", label: "Building identifiers (catalog)" },
  { key: "placeNames", label: "Place names (label overlay)" },
  {
    key: "roads",
    label: "Roads overlay",
    hint: "Reference transportation labels on imagery",
  },
  {
    key: "water",
    label: "Water bodies",
    unavailable: true,
    hint: "Dataset not integrated — use OSM2World mesh opacity to inspect ground",
  },
  {
    key: "vegetation",
    label: "Vegetation",
    unavailable: true,
    hint: "Dataset not integrated",
  },
  {
    key: "landmarks",
    label: "Landmarks",
    unavailable: true,
    hint: "Dataset not integrated",
  },
  { key: "geographicCoordinates", label: "Geographic coordinates (viewport HUD)" },
  { key: "researchAssets", label: "Research / simulation assets" },
  { key: "infrastructure", label: "Infrastructure", unavailable: true },
  { key: "customAssets", label: "Demo simulation objects (legacy toggle)" },
];

export function LayerPanel() {
  const {
    layers,
    setLayer,
    status,
    setLayersPanelOpen,
    buildingMaterialMode,
    setBuildingMaterialMode,
    proceduralGroundVisible,
    setProceduralGroundVisible,
    reconstructionMeshOpacity,
    setReconstructionMeshOpacity,
    terrainExaggerationEnabled,
    setTerrainExaggerationEnabled,
    terrainExaggeration,
    setTerrainExaggeration,
    mapMode,
  } = useViewerStore();

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-3">
        <Layers3 className="h-4 w-4 text-sky-400" />
        <h2 className="text-sm font-semibold text-slate-100">Layers</h2>
        <PanelCloseButton side="left" label="layers panel" onClose={() => setLayersPanelOpen(false)} />
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-3">
        {layerRows.map((row) => (
          <label
            key={row.key}
            className={`flex cursor-pointer flex-col rounded-md px-2 py-2 text-xs hover:bg-slate-900 ${
              row.unavailable ? "opacity-60" : "text-slate-200"
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <span>
                {row.label}
                {row.unavailable && (
                  <span className="ml-1 text-[10px] text-amber-400">(unavailable)</span>
                )}
              </span>
              <input
                type="checkbox"
                checked={layers[row.key]}
                disabled={row.unavailable}
                onChange={(e) => setLayer(row.key, e.target.checked)}
                className="accent-sky-500"
              />
            </span>
            {row.hint && <span className="mt-0.5 text-[10px] text-slate-500">{row.hint}</span>}
          </label>
        ))}

        <div className="mt-4 space-y-3 border-t border-slate-800 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Reconstruction surface
          </p>
          <label className="flex items-center justify-between text-xs text-slate-200">
            <span>Show OSM2World ground & road mesh</span>
            <input
              type="checkbox"
              checked={proceduralGroundVisible}
              onChange={(e) => setProceduralGroundVisible(e.target.checked)}
              className="accent-sky-500"
            />
          </label>
          <label className="block text-xs text-slate-300">
            Mesh opacity ({Math.round(reconstructionMeshOpacity * 100)}%)
            <input
              type="range"
              min={0.2}
              max={1}
              step={0.05}
              value={reconstructionMeshOpacity}
              onChange={(e) => setReconstructionMeshOpacity(Number(e.target.value))}
              className="mt-1 w-full accent-sky-500"
            />
          </label>
          <p className="text-[10px] leading-snug text-slate-500">
            Reduces opaque ground/road surfaces in the GLB so satellite imagery remains visible.
            Per-mesh hiding requires pipeline metadata; this adjusts the full reconstruction entity.
          </p>
        </div>

        <div className="space-y-2 border-t border-slate-800 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Building appearance
          </p>
          <select
            className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100"
            value={mapMode === "research_3d" ? "research" : buildingMaterialMode}
            disabled={mapMode === "research_3d"}
            onChange={(e) =>
              setBuildingMaterialMode(e.target.value as BuildingMaterialMode)
            }
          >
            <option value="realistic">Realistic materials</option>
            <option value="research">Research geometry</option>
          </select>
          {mapMode === "research_3d" && (
            <p className="text-[10px] text-sky-300">Research 3D map mode uses simplified materials.</p>
          )}
        </div>

        <div className="space-y-2 border-t border-slate-800 pt-3">
          <label className="flex items-center justify-between text-xs text-slate-200">
            <span>Terrain exaggeration</span>
            <input
              type="checkbox"
              checked={terrainExaggerationEnabled}
              onChange={(e) => setTerrainExaggerationEnabled(e.target.checked)}
              className="accent-sky-500"
            />
          </label>
          {terrainExaggerationEnabled && (
            <label className="block text-xs text-slate-300">
              Exaggeration ({terrainExaggeration.toFixed(2)}×)
              <input
                type="range"
                min={1}
                max={4}
                step={0.05}
                value={terrainExaggeration}
                onChange={(e) => setTerrainExaggeration(Number(e.target.value))}
                className="mt-1 w-full accent-sky-500"
              />
            </label>
          )}
        </div>
      </div>
      <div className="border-t border-slate-800 p-3 text-[11px] leading-relaxed text-slate-400">
        <p>Map mode: {mapMode}</p>
        <p>Terrain: {status.terrainSource}</p>
        <p>Imagery: {status.imagerySource}</p>
        {status.satelliteImageryDetail && <p>Satellite: {status.satelliteImageryDetail}</p>}
        <p>ArcGIS token: {status.arcGisTokenPresent ? "configured" : "optional (legacy tiles fallback)"}</p>
        <p>Ion token: {status.ionTokenPresent ? "configured" : "missing (terrain + OSM buildings)"}</p>
        <p>
          Reconstructed asset:{" "}
          {status.reconstructedAssetLoaded ? "loaded (3D GLB)" : "not generated yet — run pipeline"}
        </p>
        {status.fpsEstimate != null && <p>Render rate: ~{status.fpsEstimate} fps (1 s avg)</p>}
      </div>
    </aside>
  );
}
