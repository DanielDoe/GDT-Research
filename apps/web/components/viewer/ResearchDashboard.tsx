"use client";

import dynamic from "next/dynamic";
import { CameraControls } from "@/components/navigation/CameraControls";
import { NavigationControls } from "@/components/navigation/NavigationControls";
import { StatusBar } from "@/components/navigation/StatusBar";
import { TopBar } from "@/components/navigation/TopBar";
import { LayerPanel } from "@/components/layers/LayerPanel";
import { ObjectInspector } from "@/components/inspector/ObjectInspector";
import { PanelDock } from "@/components/viewer/PanelDock";
import { GeographicCoordinatesOverlay } from "@/components/map/GeographicCoordinatesOverlay";
import { MapStyleSelector } from "@/components/map/MapStyleSelector";
import { AgentMode } from "@/components/agents/AgentMode";
import { WeatherMapChrome } from "@/components/agents/WeatherMapChrome";
import { useViewerStore } from "@/stores/viewer-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const CesiumViewer = dynamic(
  () => import("@/components/viewer/CesiumViewer").then((m) => m.CesiumViewer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-slate-400">Loading 3D viewer…</div>
    ),
  },
);

export function ResearchDashboard() {
  const { layersPanelOpen, inspectorPanelOpen } = useViewerStore();
  const mode = useWorkspaceStore((state) => state.mode);

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <TopBar />
      {mode === "map" && (
        <>
          <NavigationControls />
          <CameraControls />
        </>
      )}
      <div className="relative flex min-h-0 flex-1">
        <div className={mode === "map" ? "flex min-h-0 min-w-0 flex-1" : "hidden"}>
          {layersPanelOpen && <LayerPanel />}
          <main className="relative min-w-0 flex-1">
            <CesiumViewer />
            <MapStyleSelector />
            <GeographicCoordinatesOverlay />
            <WeatherMapChrome />
            <PanelDock />
          </main>
          {inspectorPanelOpen && <ObjectInspector />}
        </div>
        {mode === "agents" && (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <AgentMode />
          </div>
        )}
      </div>
      <StatusBar />
    </div>
  );
}
