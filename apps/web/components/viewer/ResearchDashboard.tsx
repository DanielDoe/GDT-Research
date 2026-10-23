"use client";

import dynamic from "next/dynamic";
import { CameraControls } from "@/components/navigation/CameraControls";
import { StatusBar } from "@/components/navigation/StatusBar";
import { TopBar } from "@/components/navigation/TopBar";
import { LayerPanel } from "@/components/layers/LayerPanel";
import { ObjectInspector } from "@/components/inspector/ObjectInspector";
import { PanelDock } from "@/components/viewer/PanelDock";
import { GeographicCoordinatesOverlay } from "@/components/map/GeographicCoordinatesOverlay";
import { MapStyleSelector } from "@/components/map/MapStyleSelector";
import { useViewerStore } from "@/stores/viewer-store";

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

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <TopBar />
      <CameraControls />
      <div className="relative flex min-h-0 flex-1">
        {layersPanelOpen && <LayerPanel />}
        <main className="relative min-w-0 flex-1">
          <CesiumViewer />
          <MapStyleSelector />
          <GeographicCoordinatesOverlay />
          <PanelDock />
        </main>
        {inspectorPanelOpen && <ObjectInspector />}
      </div>
      <StatusBar />
    </div>
  );
}
