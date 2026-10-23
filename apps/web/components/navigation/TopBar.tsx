"use client";

import { Building2, Expand, Map, Settings, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  useViewerStore,
  type BuildingSourceMode,
  type InteractionTool,
  type ViewSceneMode,
} from "@/stores/viewer-store";
import { exitResearchScene } from "@/lib/agents/exit-scene";
import { useResearchAgentStore } from "@/stores/research-agent-store";
import { useWorkspaceStore, type WorkspaceMode } from "@/stores/workspace-store";

const buildingModes: { value: BuildingSourceMode; label: string }[] = [
  { value: "reference_osm", label: "Reference: Cesium OSM Buildings (ion token)" },
  { value: "gdt_reconstructed", label: "GDT: OSM2World GLB (LOD1)" },
  { value: "gdt_catalog_lod2", label: "GDT: City footprints + LiDAR heights (LOD2)" },
  { value: "none", label: "Buildings off" },
];

const tools: { value: InteractionTool; label: string }[] = [
  { value: "navigate", label: "Navigate" },
  { value: "measure", label: "Measure distance" },
  { value: "pick_coordinate", label: "Pick coordinate" },
];

export function TopBar() {
  const {
    buildingSourceMode,
    setBuildingSourceMode,
    activeScene,
    viewSceneMode,
    setViewSceneMode,
    interactionTool,
    setInteractionTool,
  } = useViewerStore();
  const mode = useWorkspaceStore((state) => state.mode);
  const setMode = useWorkspaceStore((state) => state.setMode);
  const sceneTitle = useResearchAgentStore((state) => state.mapLayer?.title);

  return (
    <header className="flex min-h-14 flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-950/90 px-4 py-2 backdrop-blur">
      <div className="flex items-center gap-3">
        <Building2 className="h-5 w-5 text-sky-400" />
        <div>
          <p className="text-sm font-semibold text-slate-100">Galveston Digital Twin</p>
          <p className="text-xs text-slate-400">GDT-Research testbed</p>
        </div>
      </div>

      <div className="flex rounded-md border border-slate-700 p-0.5">
        <Button
          type="button"
          size="sm"
          variant={mode === "map" ? "default" : "ghost"}
          className="h-8 px-3 text-xs"
          onClick={() => setMode("map" satisfies WorkspaceMode)}
        >
          <Map className="mr-1 h-3.5 w-3.5" />
          Map
        </Button>
        <Button
          type="button"
          size="sm"
          variant={mode === "agents" ? "default" : "ghost"}
          className="h-8 px-3 text-xs"
          onClick={() => setMode("agents" satisfies WorkspaceMode)}
        >
          <Users className="mr-1 h-3.5 w-3.5" />
          Agents
        </Button>
      </div>

      {sceneTitle && (
        <Button type="button" size="sm" variant="secondary" className="h-8 text-xs" onClick={exitResearchScene}>
          Exit scene
        </Button>
      )}

      {mode === "map" && (
      <div className="flex flex-wrap items-center gap-2">
        <span className="hidden text-xs text-slate-400 lg:inline">{activeScene}</span>
        <div className="flex rounded-md border border-slate-700 p-0.5">
          <Button
            type="button"
            size="sm"
            variant={viewSceneMode === "3d" ? "default" : "ghost"}
            className="h-8 px-2 text-xs"
            onClick={() => setViewSceneMode("3d" satisfies ViewSceneMode)}
          >
            3D
          </Button>
          <Button
            type="button"
            size="sm"
            variant={viewSceneMode === "2d" ? "default" : "ghost"}
            className="h-8 px-2 text-xs"
            onClick={() => setViewSceneMode("2d" satisfies ViewSceneMode)}
          >
            2D
          </Button>
        </div>

        <label className="sr-only" htmlFor="interaction-tool">
          Tool
        </label>
        <select
          id="interaction-tool"
          className="h-9 max-w-[160px] rounded-md border border-slate-700 bg-slate-900 px-2 text-xs text-slate-100"
          value={interactionTool}
          onChange={(e) => setInteractionTool(e.target.value as InteractionTool)}
        >
          {tools.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="building-source">
          Building source
        </label>
        <select
          id="building-source"
          className="h-9 max-w-[280px] rounded-md border border-slate-700 bg-slate-900 px-2 text-xs text-slate-100"
          value={buildingSourceMode}
          onChange={(e) => setBuildingSourceMode(e.target.value as BuildingSourceMode)}
        >
          {buildingModes.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
        <Button variant="secondary" size="icon" type="button" aria-label="Fullscreen">
          <Expand className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" type="button" aria-label="Settings">
          <Settings className="h-4 w-4" />
        </Button>
      </div>
      )}
    </header>
  );
}
