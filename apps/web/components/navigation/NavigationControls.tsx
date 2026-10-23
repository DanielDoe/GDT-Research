"use client";

import { Footprints, Plane, Rotate3D } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  useViewerStore,
  type NavigationMode,
  type SceneVisualizationMode,
} from "@/stores/viewer-store";
import {
  captureSceneState,
  clearPersistedScene,
  loadPersistedScene,
  savePersistedScene,
} from "@/lib/scene-persistence";
import { useSceneObjectStore } from "@/stores/scene-object-store";

const navModes: { id: NavigationMode; label: string; icon: typeof Rotate3D }[] = [
  { id: "orbit", label: "Orbit", icon: Rotate3D },
  { id: "fly", label: "Fly", icon: Plane },
  { id: "walk", label: "Walk", icon: Footprints },
];

const vizModes: { id: SceneVisualizationMode; label: string }[] = [
  { id: "satellite_only", label: "Satellite (no 3D buildings)" },
  { id: "satellite_plus_3d", label: "Satellite + 3D" },
  { id: "research_geometry", label: "Research geometry" },
  { id: "high_fidelity", label: "High fidelity (LOD3 when available)" },
];

export function NavigationControls() {
  const {
    navigationMode,
    setNavigationMode,
    sceneVisualization,
    setSceneVisualization,
    walkMoveSpeedMps,
    setWalkMoveSpeedMps,
    walkEyeHeightM,
    setWalkEyeHeightM,
    activeGeometryLod,
    hiddenBuildingIds,
    savedViews,
    restoreSceneModifications,
  } = useViewerStore();
  const sceneObjects = useSceneObjectStore((s) => s.objects);
  const updateObject = useSceneObjectStore((s) => s.updateObject);

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 px-3 py-2 text-xs">
      <div className="flex items-center gap-1">
        {navModes.map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            type="button"
            size="sm"
            variant={navigationMode === id ? "default" : "secondary"}
            className="h-8 gap-1 px-2"
            onClick={() => setNavigationMode(id)}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </Button>
        ))}
      </div>

      <label className="flex items-center gap-2 text-slate-400">
        Scene
        <select
          className="h-8 max-w-[220px] rounded-md border border-slate-700 bg-slate-900 px-2 text-slate-100"
          value={sceneVisualization}
          onChange={(e) => setSceneVisualization(e.target.value as SceneVisualizationMode)}
        >
          {vizModes.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      <span className="text-slate-500">Active mesh LOD: {activeGeometryLod}</span>

      {navigationMode === "walk" && (
        <div className="flex flex-wrap items-center gap-3 text-slate-400">
          <label>
            Speed {walkMoveSpeedMps.toFixed(1)} m/s
            <input
              type="range"
              min={0.5}
              max={12}
              step={0.1}
              value={walkMoveSpeedMps}
              onChange={(e) => setWalkMoveSpeedMps(Number(e.target.value))}
              className="ml-2 w-24 accent-sky-500"
            />
          </label>
          <label>
            Eye {walkEyeHeightM.toFixed(2)} m
            <input
              type="range"
              min={1}
              max={3}
              step={0.05}
              value={walkEyeHeightM}
              onChange={(e) => setWalkEyeHeightM(Number(e.target.value))}
              className="ml-2 w-20 accent-sky-500"
            />
          </label>
          <span className="text-[10px] text-amber-200/90">
            WASD move · hold left-drag look · terrain clamp only (no building collision)
          </span>
        </div>
      )}

      <div className="ml-auto flex gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            savePersistedScene(
              captureSceneState(
                { hiddenBuildingIds, savedViews },
                sceneObjects,
              ),
            );
          }}
        >
          Save scenario
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            const data = loadPersistedScene();
            if (!data) return;
            restoreSceneModifications(data.hiddenBuildingIds);
            for (const patch of data.sceneObjectPatches) {
              updateObject(patch.id, patch);
            }
          }}
        >
          Restore scenario
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => clearPersistedScene()}>
          Clear saved
        </Button>
      </div>
    </div>
  );
}
